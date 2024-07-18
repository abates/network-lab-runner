#!/usr/bin/env python3
"""Invoke tasks to run this lab"""

import base64
from contextlib import contextmanager
import json
import os
import random
from typing import Dict, Set
from invoke.collection import Collection
from invoke.context import Context
from invoke.tasks import task as invoke_task

class MergeCollection(Collection):
    def add_collection(self, coll: Collection, name: str, default: bool):
        return super().add_collection(coll, name, default)

namespace = Collection("automation_lab_demo")
namespace.configure(
    {
        "automation_lab_demo": {
            "debug": False,
            "infrastructure": {
                "do_token": "",
                "region": "nyc3",
                "k8s_size": "s-2vcpu-4gb",
                "k8s_clustername": "nautobot",
                "k8s_version": "1.30.2-do.0",
                "k8s_poolname": "worker-pool",
                "k8s_node_count": 4,
            },
            "deployment": {
                "do_dns_token": None,
                "nautobot_hostname": None,
                "lab_domain": None,
                "cert_manager_contact": None,
                "nautobot_image_registry": "ghcr.io",
                "nautobot_image_repository": "nautobot/nautobot",
                "nautobot_image_tag": "latest",
            }
        }
    }
)

def task(function=None, *args, **kwargs):  # pylint: disable=keyword-arg-before-vararg
    """Task decorator to override the default Invoke task decorator."""

    def task_wrapper(function=None):
        """Wrap invoke.task to add the task to the namespace as well."""
        if args or kwargs:
            task_func = invoke_task(*args, **kwargs)(function)
        else:
            task_func = invoke_task(function)
        namespace.add_task(task_func)
        return task_func

    if function:
        # The decorator was called with no arguments
        return task_wrapper(function)
    # The decorator was called with arguments
    return task_wrapper


def run(context, cmd, env: Dict = None):
    if isinstance(cmd, list):
        cmd = " ".join(cmd)
    return context.run(cmd, hide="out", echo=context.automation_lab_demo.debug, env=env)

def get_kube_namespaces(context: Context) -> Set[str]:
    namespaces = kubectl(context, "get namespaces")
    return {item["metadata"]["name"] for item in namespaces["items"]}

def ensure_namespace(context, namespace):
    if namespace and namespace not in get_kube_namespaces(context):
        run(context, f"kubectl create namespace {namespace}")

def kubectl(context: Context, command, namespace=None, parse_output=True):
    k_cmd = ["kubectl"]
    if namespace:
        k_cmd.extend(["-n", namespace])
    k_cmd.append(command)
    if parse_output:
        k_cmd.extend(["-o", "json"])
        return json.loads(run(context, k_cmd).stdout)
    run(context, k_cmd)

def kubectl_exec(context: Context, pod, command, namespace=None, container=None):
    e_cmd = [
        "exec",
        pod,
    ]
    if container:
        e_cmd.extend(["-c", container])
    if isinstance(command, list):
        command = " ".join(command)
    e_cmd.extend(["--", command])
    kubectl(context, " ".join(e_cmd), namespace=namespace, parse_output=False)

def kubectl_exec_sh(context: Context, pod, command, namespace=None, container=None):
    if isinstance(command, list):
        command = " && ".join(command)
    kubectl_exec(context, pod, f"sh -c '{command}'", container="nautobot", namespace=namespace)

def wait_rollout_status(context: Context, namespace=None):
    cmd = ["kubectl"]
    if namespace:
        cmd.extend(["-n", namespace])
    cmd.extend(["rollout", "status", "deployment"])
    run(context, " ".join(cmd))

def helm(context: Context, command, values_file=None, namespace=None):
    h_cmd = ["helm"]
    if namespace:
        ensure_namespace(context, namespace)
        h_cmd.extend(["--namespace", namespace])
    h_cmd.append(command)
    if values_file:
        h_cmd.extend(["-f", values_file])
    return run(context, h_cmd).stdout

def tofu(context: Context, command, env: Dict):
    t_cmd = ["tofu"]
    t_cmd.append(command)

    env = {f"TF_VAR_{key}": str(var) for key, var in env.items()}
    return run(context, t_cmd, env=env).stdout

def relative_path(name):
    wd = os.path.dirname(__file__)
    return os.path.normpath(os.path.join(wd, name))

def helm_list(context) -> Dict[str, str]:
    result = helm(context, "list --all-namespaces -o json")
    return {item["namespace"]: item["name"] for item in json.loads(result)}

def tofu_factory(cmd, component):
    def run_cmd(context):
        with context.cd(os.path.join(os.path.dirname(__file__), component)):
            tofu(context, f"{cmd} -auto-approve", context.automation_lab_demo[component])

    run_cmd.__name__ = f"{cmd}_{component}"
    return run_cmd

for component in ["infrastructure", "deployment"]:
    for cmd in ["apply", "destroy"]:
        run_cmd = tofu_factory(cmd, component)
        task(run_cmd)

@task(pre=[namespace.tasks["apply-infrastructure"], namespace.tasks["apply-deployment"]])
def apply(context):
    pass

@task(pre=[namespace.tasks["destroy-deployment"], namespace.tasks["destroy-infrastructure"]])
def destroy(context):
    pass

@task
def restart_nautobot(context):
    kubectl(context, "rollout restart", namespace="nautobot")

@task
def display_admin_password(context, json_output=False):
    environment = kubectl(context, "get secret nautobot-env", namespace="nautobot")
    password = base64.b64decode(environment["data"]["NAUTOBOT_SUPERUSER_PASSWORD"]).decode("utf-8")
    token = base64.b64decode(environment["data"]["NAUTOBOT_SUPERUSER_API_TOKEN"]).decode("utf-8")
    if json_output:
        print(json.dumps({"username": "admin", "password": password, "token": token}))
    else:
        print("Username: admin")
        print(f"Password: {password}")
        print(f"   Token: {token}")

def get_pod(context: Context, component):
    output = kubectl(context, f"get pods -o json -l app.kubernetes.io/component={component}", namespace="nautobot", parse_output=True)
    pod_names = [item["metadata"]["name"] for item in output["items"]]
    return pod_names[random.randint(0, len(pod_names)-1)]

@contextmanager
def copy_to_remote(context, src_path, dst_pod, dst_path, container=None, namespace=None):
    command = [
        "cp",
    ]
    if container:
        command.extend(["-c", container])

    dst_path = f"{dst_pod}:{dst_path}"
    command.extend([src_path, dst_path])

    kubectl(context, " ".join(command), namespace=namespace, parse_output=False)
    yield
    kubectl_exec(context, dst_pod, f"rm -rf {dst_path}", namespace=namespace, container=container)


def copy_from_remote(context, src_pod, src_path, dst_path, container=None, namespace=None):
    command = [
        "cp",
    ]

    if container:
        src_path = f"{src_pod}:{src_path}"
    else:
        src_path = f"{src_pod}:{src_path}"
    command.extend([src_path, dst_path])
    kubectl(context, " ".join(command), namespace=namespace, parse_output=False)


@task
def load_fixtures(context):
    """Load sample data for development."""
    pod = get_pod(context, "nautobot-default")
    with copy_to_remote(context, "fixtures", pod, "/tmp/fixtures", container="nautobot", namespace="nautobot"):
        commands = [
            "cd /tmp/fixtures",
            "nautobot-server runscript --pythonpath scripts/ load_fixtures"
        ]
        kubectl_exec_sh(context, pod, commands, container="nautobot", namespace="nautobot")


@task
def generate_fixtures(context):
    """Generate the sample data sets from the currrent database."""
    pod = get_pod(context, "nautobot-default")
    with copy_to_remote(context, "fixtures", pod, "/tmp/fixtures", container="nautobot", namespace="nautobot"):
        commands = [
            "cd /tmp/fixtures",
            "nautobot-server runscript --pythonpath scripts/ generate_fixtures"
        ]
        kubectl_exec_sh(context, pod, commands, container="nautobot", namespace="nautobot")
        kubectl_exec(context, pod, "rm -rf /tmp/fixtures/scripts", container="nautobot", namespace="nautobot")
        copy_from_remote(context, pod, "/tmp/fixtures", "fixtures", namespace="nautobot", container="nautobot")
