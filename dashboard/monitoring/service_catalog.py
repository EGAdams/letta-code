"""Server-owned service catalog; request parameters never become commands."""
from pathlib import Path
import shlex

from pydantic import ValidationError

from monitoring.service_management_models import ServiceDefinition
from monitoring.worker_lanes import LANES

CONFIG_PATH = Path.home() / '.config/factory-ops/env'


def configured_services(path: Path = CONFIG_PATH) -> tuple[list[ServiceDefinition], str]:
    services = [
        ServiceDefinition(key='factory-api', label='API Service', unit='factory-ops-api.service'),
        ServiceDefinition(key='factory-watchdog', label='Watchdog Service', unit='factory-ops-watch.service'),
    ]
    settings = {}
    error = ''
    try:
        # Only read the two non-secret settings needed for the catalog. Do not
        # source this file or include its contents in an exception/response.
        for line in path.read_text(encoding='utf-8').splitlines():
            key, separator, value = line.strip().partition('=')
            if separator and key in {'FACTORY_OPS_WORKER_UNIT', 'FACTORY_OPS_SYSTEMD_SCOPE'}:
                words = shlex.split(value, comments=True)
                settings[key] = words[0] if len(words) == 1 else ''
        configured = ServiceDefinition(
            key='configured-worker', label='Configured Worker',
            unit=settings.get('FACTORY_OPS_WORKER_UNIT', 'agent-bridge-worker.service'),
            scope=settings.get('FACTORY_OPS_SYSTEMD_SCOPE', 'system').strip().lower())
        services.append(configured)
    except FileNotFoundError:
        error = 'Factory Ops configuration is missing; its worker target cannot be verified.'
    except (OSError, UnicodeError, ValueError, ValidationError):
        error = 'Factory Ops worker configuration is unreadable or invalid.'
    seen = {(item.scope, item.unit) for item in services}
    for lane in LANES:
        if ('user', lane.service) not in seen:
            services.append(ServiceDefinition(
                key=f'worker-{lane.name}', label=f'{lane.name.title()} Worker', unit=lane.service))
            seen.add(('user', lane.service))
        elif any(item.key == 'configured-worker' and item.unit == lane.service
                 and item.scope == 'user' for item in services):
            index = next(i for i, item in enumerate(services) if item.key == 'configured-worker')
            services[index] = services[index].model_copy(update={'label': f'{lane.name.title()} Worker'})
    return services, error
