param(
  [string]$ContainerName = "",
  [string]$NewImage = "letta/letta:0.18.4",
  [int]$Port = 8283
)

  $ErrorActionPreference = "Stop"

  function Get-LettaContainer {
    param(
      [string]$Name,
      [int]$PublishedPort
    )

    if ($Name) {
      $id = docker ps -aq --filter "name=^${Name}$"
      if (-not $id) {
        throw "Container not found: $Name"
      }
      return $id | Select-Object -First 1
    }

    $candidates = docker ps --format '{{.ID}} {{.Image}} {{.Names}} {{.Ports}}'
    foreach ($line in $candidates) {
      if ($line -match "0\.0\.0\.0:$PublishedPort->" -or $line -match "\[::\]:$PublishedPort->" -or $line -match ":$PublishedPort->")
  {
        return ($line -split ' ')[0]
      }
    }

    $fallback = docker ps -q --filter "ancestor=letta/letta"
    if ($fallback) {
      return $fallback | Select-Object -First 1
    }

    throw "Could not find a running Letta container exposing port $PublishedPort"
  }

Write-Host "=== Locating Letta container ==="
$containerId = Get-LettaContainer -Name $ContainerName -PublishedPort $Port
$inspect = docker inspect $containerId | ConvertFrom-Json
$container = $inspect[0]
$name = $container.Name.TrimStart("/")
  $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
  $backupDir = Join-Path $env:USERPROFILE "Desktop\letta-upgrade-$timestamp"
  New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

Write-Host "Container: $name ($containerId)"
Write-Host "Backup dir: $backupDir"
Write-Host "Current image: $($container.Config.Image)"
Write-Host "Target image: $NewImage"

  Write-Host "`n=== Saving inspect and logs ==="
  docker inspect $containerId | Out-File -Encoding utf8 (Join-Path $backupDir "docker-inspect.json")
  docker logs --tail 500 $containerId 2>&1 | Out-File -Encoding utf8 (Join-Path $backupDir "docker-logs.txt")

  $mounts = @($container.Mounts)
  $pgMount = $mounts | Where-Object { $_.Destination -eq "/var/lib/postgresql/data" } | Select-Object -First 1
  if (-not $pgMount) {
    throw "No Postgres data mount found at /var/lib/postgresql/data. Aborting to avoid data loss."
  }

  Write-Host "`n=== Postgres mount ==="
  $pgMount | ConvertTo-Json -Depth 5

  $oldImage = $container.Config.Image
  $backupName = "$name-backup-$timestamp"

  $args = @("run", "-d", "--name", $name)

  if ($container.HostConfig.RestartPolicy.Name) {
    $args += @("--restart", $container.HostConfig.RestartPolicy.Name)
  }

  if ($container.HostConfig.NetworkMode -and $container.HostConfig.NetworkMode -ne "default") {
    $args += @("--network", $container.HostConfig.NetworkMode)
  }

  foreach ($envVar in @($container.Config.Env)) {
    $args += @("-e", $envVar)
  }

  foreach ($mount in $mounts) {
    if ($mount.Type -eq "bind") {
      $args += @("-v", "$($mount.Source):$($mount.Destination)")
    } elseif ($mount.Type -eq "volume") {
      $args += @("-v", "$($mount.Name):$($mount.Destination)")
    }
  }

  foreach ($entry in $container.HostConfig.PortBindings.PSObject.Properties) {
    $containerPort = $entry.Name
    foreach ($binding in @($entry.Value)) {
      $hostIp = $binding.HostIp
      $hostPort = $binding.HostPort
      if ($hostIp -and $hostIp -ne "0.0.0.0" -and $hostIp -ne "::") {
        $args += @("-p", "${hostIp}:${hostPort}:${containerPort}")
      } else {
        $args += @("-p", "${hostPort}:${containerPort}")
      }
    }
  }

  $args += $NewImage

  if ($container.Config.Cmd) {
    $args += @($container.Config.Cmd)
  }

  Write-Host "`n=== Pulling new image ==="
  docker pull $NewImage

  Write-Host "`n=== Renaming existing container to backup name ==="
  docker stop $name
  docker rename $name $backupName

  Write-Host "`n=== Starting upgraded container ==="
  & docker @args

  Start-Sleep -Seconds 5

Write-Host "`n=== Verifying server ==="
try {
  $resp = Invoke-WebRequest "http://localhost:$Port/openapi.json" -UseBasicParsing
  $json = $resp.Content | ConvertFrom-Json
  Write-Host "New Letta API version: $($json.info.version)"
  if ([version]$json.info.version -lt [version]"0.18.0") {
    Write-Warning "Server is still below 0.18.0. Git-backed memfs may still be unavailable."
  }
} catch {
  Write-Warning "Could not verify http://localhost:$Port/openapi.json"
}

  Write-Host "`nUpgrade complete."
  Write-Host "Old container preserved as: $backupName"
  Write-Host "Backups saved in: $backupDir"
