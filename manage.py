#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import subprocess
import time

def start_docker_desktop():
    try:
        subprocess.run("docker info", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("Starting Docker Desktop...")
        subprocess.Popen(
            r'start "" "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"',
            shell=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(10) 
        print("Docker is running.")
        


def main():
    """Run administrative tasks."""
    if "runserver" in sys.argv:
        start_docker_desktop()
        
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
