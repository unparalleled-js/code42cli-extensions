import click
import json

import code42cli.profile as cliprofile
from code42cli.extensions import script
from code42cli.extensions import sdk_options
from code42cli.util import parse_timestamp
from py42.exceptions import Py42ChecksumNotFoundError

from j42_alerts import create_simple_query, get_alert_aggregate_data
from j42_click_ext import PromptChoice
from j42_devices import create_device_data
from j42_profile import set_default_profile
from j42_util import output_pretty, get_default_search_timestamp


@click.group(name="jules")
@sdk_options
def jules(state):
    """Custom Code42 commands by Juliya Smith and inspired from other Code42 products."""
    # A lot of the logic in this extension is inspired from use-cases such as the Splunk integration,
    # or the Splunk SOAR integration.
    pass


@jules.command()
@sdk_options
def list_managers(state):
    """Lists all managers along with their managed employees."""
    sdk = state.sdk
    users_generator = sdk.users.get_all()
    managers = {}
    for response in users_generator:
        users = response.data.get("users", [])
        for user in users:
            user_id = user["userUid"]
            username = user["username"]
            profile_response = sdk.detectionlists.get_user_by_id(user_id)
            manager_username = profile_response.data.get("managerUsername")
            if manager_username:
                if manager_username not in managers:
                    managers[manager_username] = [username]
                else:
                    managers[manager_username].append(username)

    output_pretty(managers)


@jules.command()
@sdk_options
def list_orgs(state):
    """Lists the organizations."""
    gen = state.sdk.orgs.get_all()
    for response in gen:
        org_list = response["orgs"]
        for org in org_list:
            data = json.dumps(org, indent=2)
            click.echo(data)


@jules.command()
@sdk_options
@click.argument("org_id")
def show_org(state, org_id):
    """Show information about an Organization."""
    org = state.sdk.orgs.get_by_uid(org_id)
    data = json.dumps(org.data, indent=2)
    click.echo(data)


@jules.command()
@sdk_options
def verify_audit_log_dates(state):
    """Seek for audit log event timestamp formats that we don't handle correctly."""
    gen = state.sdk.auditlogs.get_all()
    for response in gen:
        events = response["events"]
        for event in events:
            timestamp = event["timestamp"]
            try:
                parse_timestamp(timestamp)
            except ValueError:
                click.echo("FOUND ONE!")
                click.echo(event)


@jules.command()
@sdk_options
def devices_health(state):
    """Show a device health report."""
    sdk = state.sdk
    generator = sdk.devices.get_all(include_backup_usage=True, active=True)
    for response in generator:
        devices = response["computers"]
        for device in devices:
            device_data = create_device_data(sdk, device)
            output_pretty(device_data)


@jules.command()
@sdk_options
@click.option("--md5", help="The MD5 hash of the file to download.")
@click.option("--sha256", help="The SHA256 hash of the file to download.")
@click.option("--save-as", help="The name of the file to save as.", default="download")
def download(state, md5, sha256, save_as):
    """Download a file from Code42."""
    try:
        if md5:
            response = state.sdk.securitydata.stream_file_by_md5(md5)
        elif sha256:
            response = state.sdk.securitydata.stream_file_by_sha256(sha256)
        else:
            raise click.ClickException("Missing one of required md5 or sha256 options.")
    except Py42ChecksumNotFoundError as err:
        click.echo(str(err), err=True)
        return

    with open(save_as, "w") as f:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                f.write(str(chunk))


@jules.command()
def select_profile():
    """Set a profile as the default by selecting it from a list."""
    profiles = cliprofile.get_all_profiles()
    profile_names = [profile_choice.name for profile_choice in profiles]
    choices = PromptChoice(profile_names)
    choices.print_choices()
    prompt_message = "Input the number of the profile you wish to use"
    profile_name = click.prompt(prompt_message, type=choices)
    set_default_profile(profile_name)


@jules.command()
@sdk_options
@click.argument("alert_id")
def show_alert_aggregate(state, alert_id):
    """Show an aggregated alert details view."""
    alert_data = get_alert_aggregate_data(state.sdk, alert_id)
    output_pretty(alert_data)


@jules.command()
@sdk_options
def list_alert_urls(state):
    """Show an aggregated alert details view."""
    sdk = state.sdk
    query = create_simple_query()
    page_num = 1
    response = sdk.alerts.search(query, page_num=page_num)
    alerts = response["alerts"]
    while len(response["alerts"]) >= 500:
        page_num += 1
        response = sdk.alerts.search(query, page_num=page_num)
        alerts.extend(response.data["alerts"])

    alert_ids = [a["id"] for a in alerts]
    for alert_id in alert_ids:
        alert_data = get_alert_aggregate_data(sdk, alert_id)
        data = {
            "id": alert_data["id"],
            "ffsUrl": alert_data["ffsUrlEndpoint"],
            "alertUrl": alert_data["alertUrl"]
        }
        output_pretty(data)


@jules.command()
@sdk_options
def audit_log_total(state):
    """Show the total number of audit log events."""
    begin_time = get_default_search_timestamp(days=2)
    total_count = 0
    generator = state.sdk.auditlogs.get_all(begin_time=begin_time)
    for response in generator:
        if "events" in response.data:
            total_count += len(response.data["events"])

    click.echo(total_count)


if __name__ == "__main__":
    script.add_command(jules)
    script()
