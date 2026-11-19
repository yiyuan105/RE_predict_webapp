#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import socket
import sys
import threading
import time
import webbrowser


def _browser_target(args):
    """从 runserver 参数中取出 host / port，默认 127.0.0.1:8000。"""
    host, port = '127.0.0.1', 8000
    for arg in args:
        if arg.startswith('-'):
            continue
        addr = arg
        if ':' in addr:
            host_part, port_part = addr.rsplit(':', 1)
            if host_part and host_part not in ('0.0.0.0', '::', '0'):
                host = host_part.strip('[]')
        else:
            port_part = addr
        if port_part.isdigit():
            port = int(port_part)
        break
    return host, port


def _open_page_when_ready(host, port):
    """等开发服务器真正开始监听后，再打开前端页面。"""
    url_host = f'[{host}]' if ':' in host else host
    for _ in range(240):
        try:
            with socket.create_connection((host, port), timeout=1):
                webbrowser.open(f'http://{url_host}:{port}/')
                return
        except OSError:
            time.sleep(0.5)


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # 运行 runserver 时自动打开前端页面（自动重载时只在父进程执行一次）
    if sys.argv[1:2] == ['runserver'] and os.environ.get('RUN_MAIN') != 'true':
        host, port = _browser_target(sys.argv[2:])
        threading.Thread(
            target=_open_page_when_ready,
            args=(host, port),
            daemon=True,
        ).start()

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
