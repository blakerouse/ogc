import sys

import arrow
import click
from rich.console import Console
from rich.table import Table

from ogc import db, state
from ogc.log import Logger as log

from ..provision import choose_provisioner
from .base import cli

console = Console(record=True)


@click.command(help="List nodes in your inventory")
@click.option("--by-tag", required=False, help="List nodes by tag")
@click.option(
    "--by-name",
    required=False,
    help="List nodes by name, this can be a substring match",
)
@click.option(
    "--output-file",
    required=False,
    help="Stores the table output to svg or html. Determined by the file extension.",
)
def ls(by_tag, by_name, output_file):
    if by_tag and by_name:
        log.error(
            "Combined filtered options are not supported, please choose one.",
        )
        sys.exit(1)

    user = db.get_user().unwrap_or_else(log.fatal)
    if not user:
        sys.exit(1)

    rows = None
    if by_tag:
        rows = [node for node in user.nodes if by_tag in node.layout.tags]
    elif by_name:
        rows = [node for node in user.nodes if node.instance_name == by_name]
    else:
        rows = user.nodes
    rows_count = len(rows)

    table = Table(title=f"Node Count: [green]{rows_count}[/]")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Provider")
    table.add_column("Created")
    table.add_column("Status")
    table.add_column("Connection")
    table.add_column("Tags")
    table.add_column("Actions")

    for data in rows:
        completed_actions = []
        failed_actions = []
        for action in data.actions:
            if action.exit_code != 0:
                failed_actions.append(action)
            else:
                completed_actions.append(action)
        table.add_row(
            data.instance_id,
            data.instance_name,
            data.layout.provider,
            arrow.get(data.created).humanize(),
            data.instance_state,
            f"ssh -i {data.layout.ssh_private_key} {data.layout.username}@{data.public_ip}",
            ",\n".join(
                [
                    f"[bold green]{tag}[/]" if by_tag and tag == by_tag else tag
                    for tag in data.layout.tags
                ]
            ),
            (
                f"pass: {'[green]:heavy_check_mark:[/]' if not failed_actions else len(completed_actions)} "
                f"fail: [red]{str(len(failed_actions)) if len(failed_actions) > 0 else len(failed_actions)}[/]"
            ),
        )

    console.print(table, justify="center")
    if output_file:
        if output_file.endswith("svg"):
            console.save_svg(output_file, title="Node List Output")
        elif output_file.endswith("html"):
            console.save_html(output_file)
        else:
            log.error(
                f"Unknown extension for {output_file}, must end in '.svg' or '.html'"
            )
            sys.exit(1)


@click.option("--provider", default="aws", help="Provider to query")
@click.option("--filter", required=False, help="Filter by keypair name")
@click.command(help="List keypairs")
def ls_key_pairs(provider, filter):
    engine = choose_provisioner(provider, env=state.app.env)
    kps = []
    if filter:
        kps = [kp for kp in engine.list_key_pairs() if filter in kp.name]
    else:
        kps = list(engine.list_key_pairs())

    for kp in kps:
        click.secho(kp.name, fg="green")


cli.add_command(ls)
cli.add_command(ls_key_pairs)
