import zipfile
import json
import sys
import os

def extract_sb3(sb3_path, extract_dir="temp_project"):
    if os.path.exists(extract_dir):
        import shutil
        shutil.rmtree(extract_dir)
    with zipfile.ZipFile(sb3_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    return os.path.join(extract_dir, "project.json")

def load_project(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def escape_c_string(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')

def gen_condition(block):
    op = block.get("opcode")
    if op == "sensing_keypressed":
        key = block["inputs"]["KEY_OPTION"][1][1]
        mapping = {
            "space": "KEY_A",
            "left arrow": "KEY_LEFT",
            "right arrow": "KEY_RIGHT",
            "up arrow": "KEY_UP",
            "down arrow": "KEY_DOWN"
        }
        return f"(kHeld & {mapping.get(key, 'KEY_A')})"
    elif op == "operator_equals":
        input1 = block["inputs"]["OPERAND1"][1][1]
        input2 = block["inputs"]["OPERAND2"][1][1]
        try:
            float(input1)
            float(input2)
            return f"({input1} == {input2})"
        except ValueError:
            return f'(strcmp("{escape_c_string(input1)}", "{escape_c_string(input2)}") == 0)'
    return "0"

def process_blocks(blocks, start_block_id, sprite_index):
    lines = []
    current_id = start_block_id
    while current_id:
        block = blocks[current_id]
        op = block["opcode"]

        def input_val(name):
            return block["inputs"][name][1][1]

        if op == "motion_movesteps":
            lines.append(f"    sprites[{sprite_index}].x += {input_val('STEPS')};")
        elif op == "motion_turnright":
            lines.append(f"    sprites[{sprite_index}].y += {input_val('DEGREES')} / 10;")
        elif op == "motion_turnleft":
            lines.append(f"    sprites[{sprite_index}].y -= {input_val('DEGREES')} / 10;")
        elif op == "motion_setx":
            lines.append(f"    sprites[{sprite_index}].x = {input_val('X')};")
        elif op == "motion_sety":
            lines.append(f"    sprites[{sprite_index}].y = {input_val('Y')};")
        elif op == "motion_changexby":
            lines.append(f"    sprites[{sprite_index}].x += {input_val('DX')};")
        elif op == "motion_changeyby":
            lines.append(f"    sprites[{sprite_index}].y += {input_val('DY')};")
        elif op == "control_wait":
            ms = int(float(input_val("DURATION")) * 1000)
            lines.append("    consoleUpdate(NULL);")
            lines.append(f"    svcSleepThread({ms} * 1000000ULL);")
        elif op == "looks_say":
            msg = escape_c_string(input_val("MESSAGE"))
            lines.append(f'    printf("Sprite {sprite_index} says: {msg}\\n");')
        elif op == "motion_glidesecstoxy":
            dur = float(input_val("SECS"))
            x = int(input_val("X"))
            y = int(input_val("Y"))
            steps = 30
            interval = dur / steps
            lines.append(f"    for (int s=0; s<{steps}; s++) {{")
            lines.append(f"        sprites[{sprite_index}].x += ({x} - sprites[{sprite_index}].x)/({steps} - s);")
            lines.append(f"        sprites[{sprite_index}].y += ({y} - sprites[{sprite_index}].y)/({steps} - s);")
            lines.append(f"        consoleUpdate(NULL);")
            lines.append(f"        svcSleepThread({int(interval*1e9)}ULL);")
            lines.append("    }")
        elif op == "control_repeat":
            times = int(input_val("TIMES"))
            substack_id = block["inputs"]["SUBSTACK"][1]
            lines.append(f"    for (int i=0; i<{times}; i++) {{")
            if substack_id and substack_id in blocks:
                lines.extend(process_blocks(blocks, substack_id, sprite_index))
            lines.append("    }")
        elif op == "control_if":
            condition_block_id = block["inputs"]["CONDITION"][1]
            cond_str = "0"
            if condition_block_id in blocks:
                cond_str = gen_condition(blocks[condition_block_id])
            substack_id = block["inputs"]["SUBSTACK"][1]
            lines.append(f"    if ({cond_str}) {{")
            if substack_id and substack_id in blocks:
                lines.extend(process_blocks(blocks, substack_id, sprite_index))
            lines.append("    }")
        # You can add more opcodes here...

        current_id = block.get("next")
    return lines

def generate_c_code(project):
    code_lines = [
        "#include <switch.h>",
        "#include <stdio.h>",
        "#include <string.h>",
        "#include <pthread.h>",
        "",
        "typedef struct {",
        "    int x;",
        "    int y;",
        "} Sprite;",
        "",
        "#define NUM_SPRITES {}".format(len([t for t in project['targets'] if not t.get('isStage', False)])),
        "Sprite sprites[NUM_SPRITES];",
        "pthread_t sprite_threads[NUM_SPRITES];",
        "",
    ]

    # Generate thread functions for each sprite
    for i, sprite in enumerate(project["targets"]):
        if sprite.get("isStage", False):
            continue

        code_lines.append(f"void* sprite_thread_{i}(void* arg) {{")
        code_lines.append(f"    sprites[{i}].x = {int(sprite.get('x', 0))};")
        code_lines.append(f"    sprites[{i}].y = {int(sprite.get('y', 0))};")

        blocks = sprite["blocks"]
        start_blocks = [b for b in blocks.values() if b.get("opcode") == "event_whenflagclicked"]
        for start_block in start_blocks:
            next_id = start_block.get("next")
            if next_id and next_id in blocks:
                code_lines.extend(process_blocks(blocks, next_id, i))

        code_lines.append("    return NULL;")
        code_lines.append("}")
        code_lines.append("")

    # Main function
    code_lines.extend([
        "int main() {",
        "    consoleInit(NULL);",
        "    consoleClear();",
        "",
    ])

    num_sprites = len([t for t in project["targets"] if not t.get("isStage", False)])
    for i in range(num_sprites):
        code_lines.append(f"    pthread_create(&sprite_threads[{i}], NULL, sprite_thread_{i}, NULL);")

    code_lines.append("    while (appletMainLoop()) {")
    code_lines.append("        u64 kDown = hidKeysDown(CONTROLLER_P1_AUTO);")
    code_lines.append("        u64 kHeld = hidKeysHeld(CONTROLLER_P1_AUTO);")
    code_lines.append("        hidScanInput();")
    code_lines.append("        consoleUpdate(NULL);")
    code_lines.append("    }")

    for i in range(num_sprites):
        code_lines.append(f"    pthread_join(sprite_threads[{i}], NULL);")

    code_lines.extend([
        "    consoleExit(NULL);",
        "    return 0;",
        "}"
    ])

    return "\n".join(code_lines)

def save_c_code(c_code, output_file="main.c"):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(c_code)

def main():
    if len(sys.argv) < 2:
        print("Использование: python compiler.py project.sb3")
        return
    sb3_path = sys.argv[1]
    json_path = extract_sb3(sb3_path)
    project = load_project(json_path)
    c_code = generate_c_code(project)
    save_c_code(c_code)
    print("✅ C-код сгенерирован в main.c")

if __name__ == "__main__":
    main()
