import random
import re

def roll_d100():
    return random.randint(1, 100)

def roll_d20():
    return random.randint(1, 20)

def roll_d4():
    return random.randint(1, 4)

def roll_d12():
    return random.randint(1, 12)

def roll_dice(number_of_dice, number_of_sides):
    return sum(random.randint(1, number_of_sides) for _ in range(number_of_dice))

def parse_dice_expression(expression):
    if expression[:2]=='0d':
        return 0,0
    components = re.findall(r'([+-]?\d*d\d+|[+-]\d+)', expression)

    total_result = 0
    details = []

    for component in components:
        if 'd' in component:
            if component.startswith(('+', '-')) and component[1] == 'd':
                num_dice = int(component[0] + '1')
                dice_size = int(component[2:])
            else:
                parts = component.split('d')
                num_dice = int(parts[0]) if parts[0] != '' else 1
                dice_size = int(parts[1])

            if num_dice == 0:
                details.append("0")
                continue

            result = roll_dice(abs(num_dice), dice_size)
            sign = 1 if num_dice > 0 else -1
            total_result += result * sign
            details.append(f"{result}")
        else:
            adjustment = int(component)
            total_result += adjustment
            details.append(component)

    return total_result, details

def get_bonus(player_data, skill_name, category=None):
    skill_bonus = 0
    skill_value = 0
    
    if category:
        skill_value = player_data['skills'][category].get(skill_name, 0)
        if skill_value > 0:
            skill_bonus = skill_value * 10
    else:
        skill_value = player_data['attributes'].get(skill_name, 0)
        if skill_value > 0:
            skill_bonus = skill_value * 10

    for item in player_data['inventory']['armures'] + player_data['inventory']['armes'] + player_data['inventory']['autres_objets']:
        if item['bonus_type'] == skill_name:
            skill_bonus += item['bonus_value']
    
    if category and skill_value == 0 and skill_bonus == 0:
        skill_bonus = -30
    
    return skill_bonus

def roll_with_bonus(player_data, skill_name, category=None):
    base_roll = roll_d100()
    bonus = get_bonus(player_data, skill_name, category)
    total = base_roll + bonus
    return base_roll, bonus, total
