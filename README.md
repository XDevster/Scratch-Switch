# Scratch to Nintendo Switch Compiler

This project provides a simple Python script that compiles Scratch `.sb3` projects into C code for Nintendo Switch homebrew applications using **devkitPro**.

---

## Features

- Parses Scratch 3.0 `.sb3` project files
- Converts basic Scratch blocks (motion, control, looks) into C code
- Supports automatic "green flag" start
- Includes simple Switch controller input handling (D-pad movement and exit button)
- Outputs a `main.c` file ready for compilation with devkitA64 and libnx

---

## Getting Started

### Prerequisites

- [devkitPro](https://devkitpro.org/wiki/Getting_Started) (including `devkitA64` and `libnx`)
- Python 3.x

### Installation

1. Install devkitPro and devkitA64 following the official instructions:  
   https://devkitpro.org/wiki/Getting_Started

2. Clone this repository:

```bash
git clone https://github.com/yourusername/scratch2switch.git
cd scratch2switch
