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
        "// --- Простая структура спрайта ---",
        "typedef struct {",
        "    int x;",
        "    int y;",
        "} Sprite;",
        "",
        "int main() {",
        "    consoleInit(NULL);",
        "    Sprite sprite = {240, 135};  // центр экрана 480x270 (пример)",
        "    bool running = true;",
        "    while (appletMainLoop() && running) {",
        "        hidScanInput();",
        "        u64 kDown = hidKeysDown(CONTROLLER_P1_AUTO);",
        "        u64 kHeld = hidKeysHeld(CONTROLLER_P1_AUTO);",
        "",
        "        consoleClear();",
        "        printf(\"Sprite position: (%d, %d)\\n\", sprite.x, sprite.y);",
        "        printf(\"Use D-pad to move. Press PLUS to exit.\\n\");",
        ""
    ]

    # Функция для блоков if/else с условиями — временно только по key pressed
    def gen_condition(block):
        op = block.get("opcode")
        if op == "sensing_keypressed":
            key = block["inputs"]["KEY_OPTION"][1][1]
            # Привяжем к кнопкам Switch (пример)
            mapping = {
                "space": "KEY_A",
                "left arrow": "KEY_LEFT",
                "right arrow": "KEY_RIGHT",
                "up arrow": "KEY_UP",
                "down arrow": "KEY_DOWN"
            }
            key_c = mapping.get(key, "KEY_A")  # по умолчанию A
            return f"(kHeld & {key_c})"
        return "0"

    # Вызов зеленого флага — сделаем так, что он запускается сразу
    code_lines.append("        // Запуск при green flag (автоматически)")

    for target in project["targets"]:
        blocks = target["blocks"]
        # Отфильтруем циклы (повторять), движения, условия, say и т.д.
        # Пройдём по блокам с event_whenflagclicked для порядка
        start_blocks = [b for b in blocks.values() if b.get("opcode") == "event_whenflagclicked"]
        for start_block in start_blocks:
            # Найдём следующий блок
            next_id = start_block.get("next")
            while next_id:
                block = blocks[next_id]
                op = block["opcode"]
                
                # motion_movesteps
                if op == "motion_movesteps":
                    steps = block["inputs"]["STEPS"][1][1]
                    code_lines.append(f"        sprite.x += {steps};")
                
                # motion_turnright / turnleft (движение по Y)
                elif op == "motion_turnright":
                    degrees = block["inputs"]["DEGREES"][1][1]
                    code_lines.append(f"        sprite.y += {degrees} / 10;  // упрощённо")
                elif op == "motion_turnleft":
                    degrees = block["inputs"]["DEGREES"][1][1]
                    code_lines.append(f"        sprite.y -= {degrees} / 10;  // упрощённо")

                # control_repeat
                elif op == "control_repeat":
                    times = block["inputs"]["TIMES"][1][1]
                    substack_id = block["inputs"]["SUBSTACK"][1]
                    code_lines.append(f"        for (int i=0; i<{times}; i++) {{")
                    if substack_id and substack_id in blocks:
                        sub_block = blocks[substack_id]
                        # простая рекурсия не сделана, но вызовем повторно с этим блоком
                        # чтобы не усложнять — сделаем только один уровень вложенности
                        op_sub = sub_block["opcode"]
                        if op_sub == "motion_movesteps":
                            s = sub_block["inputs"]["STEPS"][1][1]
                            code_lines.append(f"            sprite.x += {s};")
                    code_lines.append("        }")

                # control_wait
                elif op == "control_wait":
                    seconds = block["inputs"]["DURATION"][1][1]
                    ms = int(float(seconds)*1000)
                    code_lines.append(f"        consoleUpdate(NULL);")
                    code_lines.append(f"        svcSleepThread({ms} * 1000000ULL);  // ждем {seconds} сек")

                # looks_say
                elif op == "looks_say":
                    msg = block["inputs"]["MESSAGE"][1][1]
                    msg_esc = escape_c_string(msg)
                    code_lines.append(f'        printf("Say: {msg_esc}\\n");')

                # control_if
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
                            code_lines.append(f"            sprite.x += {s};")
                    code_lines.append("        }")

                # event_whenkeypressed (обработать управление)
                elif op == "event_whenkeypressed":
                    key = block["inputs"]["KEY_OPTION"][1][1]
                    mapping = {
                        "space": "KEY_A",
                        "left arrow": "KEY_LEFT",
                        "right arrow": "KEY_RIGHT",
                        "up arrow": "KEY_UP",
                        "down arrow": "KEY_DOWN"
                    }
                    key_c = mapping.get(key, "KEY_A")
                    # Пример действия при нажатии:
                    next_b = block.get("next")
                    if next_b and next_b in blocks:
                        nxt = blocks[next_b]
                        if nxt["opcode"] == "motion_movesteps":
                            s = nxt["inputs"]["STEPS"][1][1]
                            code_lines.append(f"        if (kHeld & {key_c}) sprite.x += {s};")

                # Переходим к следующему блоку
                next_id = block.get("next")

    # Добавим управление кнопками Switch для игрока (стандартно)
    code_lines.append("        // Управление с геймпада (D-pad)")
    code_lines.append("        if (kHeld & KEY_RIGHT) sprite.x += 5;")
    code_lines.append("        if (kHeld & KEY_LEFT) sprite.x -= 5;")
    code_lines.append("        if (kHeld & KEY_UP) sprite.y -= 5;")
    code_lines.append("        if (kHeld & KEY_DOWN) sprite.y += 5;")
    code_lines.append("        if (kDown & KEY_PLUS) running = false;  // Выход")

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
