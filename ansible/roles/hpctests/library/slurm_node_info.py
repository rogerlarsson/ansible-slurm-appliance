#!/usr/bin/env python

# Copyright: (c) 2020, StackHPC
# Apache 2 License

from ansible.module_utils.basic import AnsibleModule
import json

ANSIBLE_METADATA = {
    "metadata_version": "0.1",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = """
---
module: slurm_node_info
short_description: Get information about Slurm nodes
version_added: "0.0"
description:
    - "Gets all the available information from Slurm's `sinfo` command about specified nodes. The returned `info` property is a dict with keys from sinfo --All parameters and values a list of strings in specified node order."
options
    nodes:
        description:
            - Slurm nodenames for which information is required. These must be homogenous.
        required: true
        type: list
requirements:
    - "python >= 3.6"
author:
    - Steve Brasier, StackHPC
"""

EXAMPLES = """
TODO
"""


def run_module():
    module_args = dict(
        nodes=dict(type="list", required=True),
    )

    module = AnsibleModule(argument_spec=module_args, supports_check_mode=True)
    result = {"changed": False}
    if module.check_mode:
        module.exit_json(**result)
    
    node_spec = ','.join(module.params['nodes'])
    _, stdout,_ = module.run_command("sinfo --Format All --node %s" % node_spec, check_rc=True)
    lines = stdout.splitlines()
    # if len(lines) > 2:
    #     raise ValueError('Info requested for nodes which are not homogenous: %s' % lines)
    info = {}
    params = [v.strip() for v in lines[0].split('|')]
    values = [line.split('|') for line in lines[1:]]
    print(values)
    for ix, param in enumerate(params):
        info[param] = [nodeinfo[ix].strip() for nodeinfo in values]
    result['info'] = info
    
    module.exit_json(**result)


def main():
    run_module()

if __name__ == "__main__":
    main()
