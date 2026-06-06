import json
import importlib.util
import os
import datetime

def check_python_files():
    python_files = ['tasks/backlog.py', 'platform/infra/health_monitor.py']
    errors = []
    for file in python_files:
        try:
            spec = importlib.util.spec_from_file_location("module.name", file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            errors.append(f"Error importing {file}: {str(e)}")
    return errors

def check_tasks():
    with open('tasks/backlog.json') as f:
        tasks = json.load(f)
    completed = sum(1 for task in tasks if task['status'] == 'completed')
    pending = sum(1 for task in tasks if task['status'] == 'pending')
    return completed, pending

def write_health_status(errors, completed, pending):
    health_status = {
        'system_health': 'ok' if not errors else 'error',
        'task_counts': {
            'completed': completed,
            'pending': pending
        },
        'last_build_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    with open('platform/infra/health_status.json', 'w') as f:
        json.dump(health_status, f)

def main():
    errors = check_python_files()
    completed, pending = check_tasks()
    write_health_status(errors, completed, pending)

if __name__ == '__main__':
    main()
