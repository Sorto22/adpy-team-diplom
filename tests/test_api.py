from vkapi import *
from config import *
import pytest


@pytest.mark.parametrize(city_id, age_from, age_to, sex, expect (
    ,
    "1, 25, 35, 1, True",
    "1, 20, 25, 2, True",
    "1, 0, 0, 0, False",
))
def test_api(city_id, age_from, age_to, sex, expect):
    token = Config.VK_TOKEN
    vk_client = VkClient(token)
    users = vk_client.search_users(city_id, age_from, age_to, sex)
    bool_result = len(users) > 0
    assert bool_result == expected

