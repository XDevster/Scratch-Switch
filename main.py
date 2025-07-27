import zipfile
import json
import sys
import os

def extract_sb3(sb3_path, extract_dir="temp_project"):
    if os.path.exists(extract_dir):
        # Очистим папку
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

def generate_c_code(project):
    code_lines = [
        "#include <switch.h>",
        "#include <stdio.h>",
        "#include <string.h>",
        "",
        "// --- Структура спрайта ---",
        "typedef struct {",
        "    int x;",
        "    int y;",
        "} Sprite;",
        "",
        "// --- Количество спрайтов ---"
    ]

    sprites = [t for t in project["targets"] if not t.get("isStage", False)]
    code_lines.append(f"#define NUM_SPRITES {len(sprites)}")
    code_lines.append("Sprite sprites[NUM_SPRITES];")
    code_lines.append("")

    code_lines.extend([
        "int main() {",
        "    consoleInit(NULL);",
        "    bool running = true;",
        "",
        "    // Инициализация позиций спрайтов",
    ])

    for i, sprite in enumerate(sprites):
        code_lines.append(f"    sprites[{i}].x = 240;")
        code_lines.append(f"    sprites[{i}].y = 135;")

    code_lines.extend([
        "    while (appletMainLoop() && running) {",
        "        hidScanInput();",
        "        u64 kDown = hidKeysDown(CONTROLLER_P1_AUTO);",
        "        u64 kHeld = hidKeysHeld(CONTROLLER_P1_AUTO);",
        "",
        "        consoleClear();",
    ])

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
        return "0"

    # Process each sprite’s script
    for sprite_index, target in enumerate(sprites):
        blocks = target["blocks"]
        code_lines.append(f"        // --- Обработка скриптов спрайта {sprite_index} ---")
        start_blocks = [b for b in blocks.values() if b.get("opcode") == "event_whenflagclicked"]
        for start_block in start_blocks:
            next_id = start_block.get("next")
            while next_id:
                block = blocks[next_id]
                op = block["opcode"]

                if op == "motion_movesteps":
                    steps = block["inputs"]["STEPS"][1][1]
                    code_lines.append(f"        sprites[{sprite_index}].x += {steps};")

                elif op == "motion_turnright":
                    degrees = block["inputs"]["DEGREES"][1][1]
                    code_lines.append(f"        sprites[{sprite_index}].y += {degrees} / 10;")

                elif op == "motion_turnleft":
                    degrees = block["inputs"]["DEGREES"][1][1]
                    code_lines.append(f"        sprites[{sprite_index}].y -= {degrees} / 10;")

                elif op == "control_wait":
                    seconds = block["inputs"]["DURATION"][1][1]
                    ms = int(float(seconds)*1000)
                    code_lines.append(f"        consoleUpdate(NULL);")
                    code_lines.append(f"        svcSleepThread({ms} * 1000000ULL);")

                elif op == "looks_say":
                    msg = block["inputs"]["MESSAGE"][1][1]
                    code_lines.append(f'        printf("Sprite {sprite_index} says: {escape_c_string(msg)}\\n");')

                elif op == "control_repeat":
                    times = block["inputs"]["TIMES"][1][1]
                    substack_id = block["inputs"]["SUBSTACK"][1]
                    code_lines.append(f"        for (int i=0; i<{times}; i++) {{")
                    if substack_id and substack_id in blocks:
                        sub_block = blocks[substack_id]
                        if sub_block["opcode"] == "motion_movesteps":
                            s = sub_block["inputs"]["STEPS"][1][1]
                            code_lines.append(f"            sprites[{sprite_index}].x += {s};")
                    code_lines.append("        }")

                elif op == "control_if":
                    condition_block = block["inputs"]["CONDITION"][1]
                    cond_str = "0"
                    if condition_block in blocks:
                        cond_str = gen_condition(blocks[condition_block])
                    substack_id = block["inputs"]["SUBSTACK"][1]
                    code_lines.append(f"        if ({cond_str}) {{")
                    if substack_id and substack_id in blocks:
                        sub_block = blocks[substack_id]
                        if sub_block["opcode"] == "motion_movesteps":
                            s = sub_block["inputs"]["STEPS"][1][1]
                            code_lines.append(f"            sprites[{sprite_index}].x += {s};")
                    code_lines.append("        }")

                next_id = block.get("next")

    code_lines.append("        consoleUpdate(NULL);")
    code_lines.append("    }")
    code_lines.append("    consoleExit(NULL);")
    code_lines.append("    return 0;")
    code_lines.append("}")

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
