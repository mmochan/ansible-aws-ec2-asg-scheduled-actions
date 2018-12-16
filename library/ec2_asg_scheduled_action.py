# (c) 2016, Mike Mochan <@mmochan>
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
DOCUMENTATION = '''
module: ec2_asg_scheduled_actions
short_description: create, modify and delete AutoScaling Scheduled Actions.
description:
  - Read the AWS documentation for Scheduled Actions
    U(http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-as-scheduledaction.html
version_added: "2.2"
options:
  autoscaling_group_name:
    description:
      - The name of the autoscaling group.
    required: true
  scheduled_action_name:
    description:
      - The name of the scheduled action.
    required: true
  state:
    description:
      - Create, delete, accept, reject a peering connection.
    required: false
    default: present
    choices: ['present', 'absent']
author: Mike Mochan(@mmochan)
extends_documentation_fragment: aws
'''

EXAMPLES = '''
# Create a scheduled action for my autoscaling group.
- name: create a scheduled action for autoscaling group
  ec2_asg_scheduled_action:
    autoscaling_group_name: test_asg
    scheduled_action_name: mtest_asg_schedule
    start_time: 2017 August 18 08:00 UTC+10
    end_time: 2018 August 18 08:00 UTC+10
    recurrence: 40 22 * * 1-5
    min_size: 0
    max_size: 0
    desired_capacity: 0
    state: present
  register: scheduled_action

'''
RETURN = '''
task:
  description: The result of the present, and absent actions.
  returned: success
  type: dictionary
'''

try:
    import json
    import botocore
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

from dateutil.tz import tzutc
import datetime

def format_request(module):
    request = dict()
    request['AutoScalingGroupName'] = module.params.get('autoscaling_group_name')
    request['ScheduledActionName'] = module.params.get('scheduled_action_name')
    request['Recurrence'] = module.params.get('recurrence')
    request['DesiredCapacity'] = module.params.get('desired_capacity')

    if module.params.get('min_size') != None:
      request['MinSize'] = module.params.get('min_size')

    if module.params.get('max_size') != None:
      request['MaxSize'] = module.params.get('max_size')

    if module.params.get('start_time') != None:
      request['StartTime'] = module.params.get('start_time')

    if module.params.get('end_time') != None:
      request['EndTime'] = module.params.get('end_time')

    return request


def delete_scheduled_action(client, module):
    changed = False
    actions = describe_scheduled_actions(client, module)
    xx = actions.get("ScheduledUpdateGroupActions")

    if len(xx) == 0:
      return changed, actions

    changed = True
    params = dict()
    params['AutoScalingGroupName'] = module.params.get('autoscaling_group_name')
    params['ScheduledActionName'] = module.params.get('scheduled_action_name')
    try:
        actions = client.delete_scheduled_action(**params)
    except botocore.exceptions.ClientError as e:
        module.fail_json(msg=str(e))

    return changed, actions


def describe_scheduled_actions(client, module):
    actions = dict()
    try:
        actions = client.describe_scheduled_actions(
            AutoScalingGroupName=module.params.get('autoscaling_group_name'),
            ScheduledActionNames=[module.params.get('scheduled_action_name')]
        )
    except botocore.exceptions.ClientError as e:
        pass
    return actions

# The boto module requires a start and end time, and the deploy of the put sets the time it was created.
# Thus we can't really check on the times, and must pull these off the compare for changes.
# Also the startTime needs to be now or in the future, so that is unlikely to be specified in the playbook
# as aws does not allow it to be in the past! So most likely only the schedule will be specified in the playbook.
# Otherwise we need to do a fairly complex diff on what we would put against what is already there.
# So the change on startTime and EndTime is ignored and only other settings are compared.

def put_scheduled_update_group_action(client, module):
    changed = False
    params = format_request(module)

    exists = describe_scheduled_actions(client, module)
    xx = exists.get("ScheduledUpdateGroupActions")

    try:
      status = client.put_scheduled_update_group_action(**params)
    except botocore.exceptions.ClientError as e:
      module.fail_json(msg=str(e))

    if len(xx) == 0:
      changed = True
    else:
      xx = xx[0]
      exists = describe_scheduled_actions(client, module)
      yy = exists.get("ScheduledUpdateGroupActions")[0]

      for x in ['StartTime','EndTime','Time']:
        if x in xx:
           xx.pop(x)

        if x in yy:
           yy.pop(x)

      if xx != yy:
        changed = True

    return changed, status


def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(dict(
        autoscaling_group_name=dict(default=None),
        scheduled_action_name=dict(default=None),
        start_time=dict(default=None),
        end_time=dict(default=None),
        recurrence=dict(default=None),
        min_size=dict(default=None, type='int'),
        max_size=dict(default=None, type='int'),
        desired_capacity=dict(default=None, type='int'),
        state=dict(default='present', choices=['present', 'absent'])
        )
    )
    module = AnsibleModule(argument_spec=argument_spec)
    state = module.params.get('state').lower()

    if not HAS_BOTO3:
        module.fail_json(msg='json and boto3 are required.')

    try:
        region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)
        client = boto3_conn(module, conn_type='client', resource='autoscaling', region=region, endpoint=ec2_url, **aws_connect_kwargs)
    except botocore.exceptions.NoCredentialsError, e:
        module.fail_json(msg="Can't authorize connection - " + str(e))

    if state == 'present':
        (changed, results) = put_scheduled_update_group_action(client, module)
        module.exit_json(changed=changed, results=results)
    else:
        #(changed, results) = delete_scheduled_action(state, client, module)
        (changed, results) = delete_scheduled_action(client, module)
        module.exit_json(changed=changed, results=results)


# import module snippets
from ansible.module_utils.basic import *
from ansible.module_utils.ec2 import *

if __name__ == '__main__':
    main()
