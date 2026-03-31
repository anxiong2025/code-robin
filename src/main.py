from __future__ import annotations

import argparse
import os
import shlex
from pathlib import Path

from .reporter import Reporter
from .scanner import scan_project

COMMANDS = {'scan', 'arch', 'deps', 'stats', 'help'}

HELP_TEXT = """Available commands:
  scan [path]              scan a Python project and print manifest
  arch [path]              generate full architecture report
  deps [path]              analyze and print module dependencies
  stats [path]             print project statistics
  help                     show this help message
  exit / quit              exit the interactive shell

Any other input will be sent to Claude as a conversation.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='claude-code-robin',
        description='Read your codebase like Robin reads Poneglyphs — Python project architecture analyzer',
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    scan_parser = subparsers.add_parser('scan', help='scan a Python project and print manifest')
    scan_parser.add_argument('path', nargs='?', default='.', help='project root path (default: current directory)')

    arch_parser = subparsers.add_parser('arch', help='generate full architecture report')
    arch_parser.add_argument('path', nargs='?', default='.', help='project root path')
    arch_parser.add_argument('--output', '-o', help='write report to file instead of stdout')

    deps_parser = subparsers.add_parser('deps', help='analyze module dependencies')
    deps_parser.add_argument('path', nargs='?', default='.', help='project root path')

    stats_parser = subparsers.add_parser('stats', help='print project statistics')
    stats_parser.add_argument('path', nargs='?', default='.', help='project root path')

    subparsers.add_parser('interactive', help='start an interactive shell')
    return parser


def _resolve_path(path_str: str) -> Path:
    return Path(path_str).resolve()


def run_command(cmd: str) -> None:
    """Execute a command in interactive mode."""
    parts = shlex.split(cmd)
    command = parts[0]
    path = _resolve_path(parts[1]) if len(parts) > 1 else _resolve_path('.')

    if command == 'scan':
        reporter = Reporter.from_path(path)
        print(reporter.render_manifest())
    elif command == 'arch':
        reporter = Reporter.from_path(path)
        print(reporter.render_full_report())
    elif command == 'deps':
        reporter = Reporter.from_path(path)
        print(reporter.render_dependencies())
    elif command == 'stats':
        reporter = Reporter.from_path(path)
        print(reporter.render_stats())
    elif command == 'help':
        print(HELP_TEXT)
    else:
        print(f'Unknown command: {command}')
        print('Type "help" for available commands.')


def _chat_bedrock(messages: list[dict], model: str, region: str, token: str) -> str:
    import json
    import httpx

    url = f'https://bedrock-runtime.{region}.amazonaws.com/model/{model}/invoke'
    body = json.dumps({
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': 1024,
        'system': 'You are Robin, an expert Python code architecture analyst. Help users understand their codebase structure, dependencies, and design patterns. Answer concisely.',
        'messages': messages,
    })
    resp = httpx.post(url, content=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}',
    }, timeout=60)
    resp.raise_for_status()
    return json.loads(resp.text)['content'][0]['text']


def _chat_anthropic(messages: list[dict]) -> str:
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model='claude-sonnet-4-6-20250514',
        max_tokens=1024,
        system='You are Robin, an expert Python code architecture analyst. Help users understand their codebase structure, dependencies, and design patterns. Answer concisely.',
        messages=messages,
    )
    return response.content[0].text


def chat(user_input: str, history: list[dict]) -> list[dict]:
    """Send user input to Claude and manage conversation history."""
    history.append({'role': 'user', 'content': user_input})

    try:
        token = os.environ.get('AWS_BEARER_TOKEN_BEDROCK', '')
        if token and os.environ.get('CLAUDE_CODE_USE_BEDROCK') == '1':
            region = os.environ.get('AWS_REGION', 'us-east-1')
            model = os.environ.get('ANTHROPIC_DEFAULT_SONNET_MODEL', 'us.anthropic.claude-sonnet-4-6')
            reply = _chat_bedrock(history, model, region, token)
        else:
            reply = _chat_anthropic(history)
    except Exception as e:
        print(f'Error: {e}')
        history.pop()
        return history

    history.append({'role': 'assistant', 'content': reply})
    print(reply)
    return history


def interactive() -> int:
    """Run the interactive REPL."""
    print('claude-code-robin — Interactive Mode')
    print('Read your codebase like Robin reads Poneglyphs.')
    print('Type "help" for available commands, "exit" to quit.')
    print('Other input will be sent to Claude for conversation.\n')
    history: list[dict] = []
    while True:
        try:
            line = input('robin> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ('exit', 'quit'):
            break
        first_word = line.split()[0]
        if first_word in COMMANDS:
            run_command(line)
        else:
            history = chat(line, history)
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == 'interactive':
        return interactive()

    path = _resolve_path(getattr(args, 'path', '.'))
    reporter = Reporter.from_path(path)

    if args.command == 'scan':
        print(reporter.render_manifest())
        return 0

    if args.command == 'arch':
        output = reporter.render_full_report()
        if args.output:
            Path(args.output).write_text(output, encoding='utf-8')
            print(f'Report written to {args.output}')
        else:
            print(output)
        return 0

    if args.command == 'deps':
        print(reporter.render_dependencies())
        return 0

    if args.command == 'stats':
        print(reporter.render_stats())
        return 0

    parser.error(f'unknown command: {args.command}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
