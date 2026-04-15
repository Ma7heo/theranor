from __future__ import annotations


def display_skill_name(skill_name: str) -> str:
    return skill_name.replace("_", " ")


def count_allocated_skill_points(values: dict[str, dict[str, int]]) -> int:
    return sum(skill_value for category_values in values.values() for skill_value in category_values.values())


def build_skill_table_text(
    entity_data: dict,
    allocated_values: dict[str, dict[str, int]],
    category_labels: dict[str, str],
) -> str:
    attributes = entity_data["attributes"]
    category_pairs = [("force", "agilite"), ("charisme", "intelligence")]
    lines: list[str] = []

    for pair_index, (left_category, right_category) in enumerate(category_pairs):
        left_header = f"{category_labels[left_category]} ({attributes[left_category[:3]]})"
        right_header = f"{category_labels[right_category]} ({attributes[right_category[:3]]})"

        left_rows = []
        for skill_name in entity_data["skills"][left_category]:
            current_level = entity_data["skills"][left_category][skill_name]
            allocated_level = allocated_values[left_category][skill_name]
            left_rows.append(f"{display_skill_name(skill_name)}: {current_level + allocated_level}")

        right_rows = []
        for skill_name in entity_data["skills"][right_category]:
            current_level = entity_data["skills"][right_category][skill_name]
            allocated_level = allocated_values[right_category][skill_name]
            right_rows.append(f"{display_skill_name(skill_name)}: {current_level + allocated_level}")

        left_width = max([len(left_header)] + [len(row) for row in left_rows])
        right_width = max([len(right_header)] + [len(row) for row in right_rows])

        lines.append(f"{left_header.ljust(left_width)} | {right_header.ljust(right_width)}")
        lines.append(f"{'_' * left_width} | {'_' * right_width}")

        row_count = max(len(left_rows), len(right_rows))
        for row_index in range(row_count):
            left_cell = left_rows[row_index] if row_index < len(left_rows) else ""
            right_cell = right_rows[row_index] if row_index < len(right_rows) else ""
            lines.append(f"{left_cell.ljust(left_width)} | {right_cell.ljust(right_width)}")

        if pair_index == 0:
            lines.append("")

    return "```text\n" + "\n".join(lines) + "\n```"
