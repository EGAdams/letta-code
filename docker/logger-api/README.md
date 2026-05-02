# Local Logger API (Docker)

A self-contained Docker setup with PHP API + MySQL for the Letta logging system. Run this instead of relying on the HostGator remote server.

## Quick Start

From this directory:

```bash
# Start the containers
docker-compose up -d

# Verify it's running
curl http://localhost:8284/libraries/local-php-api/index.php/object/selectAll
```

The API will be available at: `http://localhost:8284/libraries/local-php-api/index.php`

## Services

- **PHP API**: Port 8284 (Apache + PHP 7.4)
- **MySQL**: Port 3306 (local connections only)

## Configuration

Environment variables (in `docker-compose.yml`):
- `DB_HOST`: mysql (container name)
- `DB_USERNAME`: tinman72_4a4e_cg
- `DB_PASSWORD`: WqA4UuFUPs8HWFnxbz
- `DB_DATABASE_NAME`: tinman72_rest_api_demo

## Using with RemoteLogger

Update `src/logger/RemoteLogger.ts`:

```typescript
const BASE_URL = process.env.LETTA_LOGGER_API ?? "http://localhost:8284/libraries/local-php-api/index.php";
```

Or set environment variable when running tests:

```bash
export LETTA_LOGGER_API="http://localhost:8284/libraries/local-php-api/index.php"
bun test
```

## Using from Other Machines on WiFi

If you need to access from other machines on your local network, expose the service by finding your machine's IP:

```bash
# Get your local IP
ifconfig | grep "inet " | grep -v 127.0.0.1

# Then use that IP instead of localhost
# e.g., http://192.168.1.100:8284/libraries/local-php-api/index.php
```

Update `docker-compose.yml` ports to expose on all interfaces:

```yaml
php-api:
  ports:
    - "0.0.0.0:8284:80"  # Listen on all interfaces instead of localhost only
```

## Logs

View PHP errors:

```bash
docker logs logger-api-php
docker logs logger-api-mysql
```

View MySQL data:

```bash
docker exec -it logger-api-mysql mysql -u root -proot tinman72_rest_api_demo
```

## Cleanup

```bash
# Stop containers
docker-compose down

# Remove data volume (fresh start next time)
docker volume rm logger_mysql_data
```

## Database

The MySQL database is automatically initialized with the `monitored_objects` table on first startup (see `mysql-init/01-init.sql`).

Schema:
```sql
CREATE TABLE `monitored_objects` (
  `id` int(100) NOT NULL AUTO_INCREMENT,
  `object_view_id` varchar(50) NOT NULL,
  `object_data` mediumtext NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `object_name` (`object_view_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
```

## Troubleshooting

**Container won't start:**
```bash
docker-compose logs -f
```

**Can't connect to MySQL:**
- Wait for health check to pass (takes ~10 seconds on first start)
- Check that port 3306 isn't already in use

**API returns 404:**
- Make sure you're using the full path: `/libraries/local-php-api/index.php`
- Verify the container is running: `docker ps`
