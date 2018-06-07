from test.integrationtests.skills.skill_tester import SkillTest

import mock

kitchen_light = {'state': 'off', 'id': '1', 'dev_name': 'kitchen'}


def test_runner(skill, example, emitter, loader):
    def execute_service(service, action, data):
        if action == 'turn_on':
            kitchen_light['state'] = 'on'
        elif action == 'turn_off':
            kitchen_light['state'] = 'off'
        print(kitchen_light)

    s = [s for s in loader.skills if s and s.root_dir == skill]

    s[0].ha = mock.MagicMock()
    s[0].ha.find_entity.return_value = kitchen_light
    s[0].ha.execute_service.side_effect = execute_service
    return SkillTest(skill, example, emitter).run(loader)
