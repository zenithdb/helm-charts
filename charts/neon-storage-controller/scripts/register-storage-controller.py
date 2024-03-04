#!/usr/bin/env python

import os
import sys
import json
import logging
import urllib.request
import urllib.error

# region_id different in console/cplan with prefix aws-<region>
REGION = os.environ["REGION_ID"]
# ZONE env will be autogenerated from init container
ZONE = os.environ["ZONE"]
HOST = os.environ["HOST"]
PORT = os.getenv("PORT", 50051)

GLOBAL_CPLANE_JWT_TOKEN = os.environ["JWT_TOKEN"]
LOCAL_CPLANE_JWT_TOKEN = os.environ["CONTROL_PLANE_JWT_TOKEN"]
CONSOLE_API_KEY = os.environ["CONSOLE_API_KEY"]

# To register new pageservers
URL_PATH = "management/api/v2/pageservers"
# To get pageservers
ADMIN_URL_PATH = "api/v1/admin/pageservers"

GLOBAL_CPLANE_URL = f"{os.environ['GLOBAL_CPLANE_URL'].strip('/')}/{URL_PATH}"
LOCAL_CPLANE_URL = f"{os.environ['LOCAL_CPLANE_URL'].strip('/')}/{URL_PATH}"
CONSOLE_URL = f"{os.environ['CONSOLE_URL']}/{ADMIN_URL_PATH}"

PAYLOAD = dict(
    host=HOST,
    region_id=REGION,
    port=6400,
    disk_size=0,
    instance_id=HOST,
    http_host=HOST,
    http_port=int(PORT),
    availability_zone_id=ZONE,
    instance_type="",
    register_reason="Storage Controller Virtual Pageserver",
    active=False,
    is_storage_controller=True,
)


def get_data(url, token, host=None):
    if host is not None:
        url = f"{url}/{host}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    # Check if the server is already registered
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as response:
            if response.getcode() == 200:
                return json.loads(response.read())
    except urllib.error.URLError:
        pass
    return {}


def get_pageserver_id(url, token):
    data = get_data(url, token, HOST)
    if "node_id" in data:
        return data["node_id"]


def get_pageserver_version():
    data = get_data(CONSOLE_URL, CONSOLE_API_KEY)
    if "data" not in data:
        return -1
    for pageserver in data["data"]:
        region_id = pageserver["region_id"]
        if region_id == REGION or region_id == f"{REGION}-new":
            return pageserver["version"]
    return -1


def register(url, token, payload):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "Python script 1.0",
    }
    data = str(json.dumps(payload)).encode()
    req = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        response = json.loads(resp.read())
    log.info(response)
    if "node_id" in response:
        return response["node_id"]


if __name__ == "__main__":
    logging.basicConfig(
        style="{",
        format="{asctime} {levelname:8} {name}:{lineno} {message}",
        level=logging.INFO,
    )

    log = logging.getLogger()

    log.info(
        json.dumps(
            dict(
                GLOBAL_CPLANE_URL=GLOBAL_CPLANE_URL,
                LOCAL_CPLANE_URL=LOCAL_CPLANE_URL,
                CONSOLE_URL=CONSOLE_URL,
                **PAYLOAD,
            ),
            indent=4,
        )
    )

    log.info("get version from existing deployed pageserver")
    version = get_pageserver_version()

    if version == -1:
        log.error(f"Unable to find pageserver version from {CONSOLE_URL}")
        sys.exit(1)

    log.info(f"found latest version={version} for region={REGION}")
    PAYLOAD.update(dict(version=version))

    log.info("check if pageserver already registered or not in console")
    node_id_in_console = get_pageserver_id(GLOBAL_CPLANE_URL, GLOBAL_CPLANE_JWT_TOKEN)

    if node_id_in_console is None:
        log.info("Registering storage controller in console")
        node_id_in_console = register(
            GLOBAL_CPLANE_URL, GLOBAL_CPLANE_JWT_TOKEN, PAYLOAD
        )
        log.info(
            f"Storage controller registered in console with node_id \
            {node_id_in_console}"
        )
    else:
        log.info(
            f"Storage controller already registered in console with node_id \
            {node_id_in_console}"
        )

    log.info("check if pageserver already registered or not in cplane")
    node_id_in_cplane = get_pageserver_id(LOCAL_CPLANE_URL, LOCAL_CPLANE_JWT_TOKEN)

    if node_id_in_cplane is None:
        PAYLOAD.update(dict(node_id=str(node_id_in_console)))
        log.info("Registering storage controller in cplane")
        node_id_in_cplane = register(LOCAL_CPLANE_URL, LOCAL_CPLANE_JWT_TOKEN, PAYLOAD)
        log.info(
            f"Storage controller registered in cplane with node_id \
            {node_id_in_cplane}"
        )
    else:
        log.info(
            f"Storage controller already registered in cplane with node_id \
            {node_id_in_cplane}"
        )
