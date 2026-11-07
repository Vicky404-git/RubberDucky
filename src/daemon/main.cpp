#include <stdexcept>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <X11/XKBlib.h>

#include <iostream>
#include <string>
#include <vector>
#include <filesystem>

#include <unistd.h>
#include <sys/wait.h>
#include <sys/types.h>
#include <cerrno>
#include <cstring>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cctype>

namespace fs = std::filesystem;

bool grab_failed = false;

std::string trim(std::string value) {
    const auto first = value.find_first_not_of(" \t\r\n");
    if (first == std::string::npos) return "";
    const auto last = value.find_last_not_of(" \t\r\n");
    return value.substr(first, last - first + 1);
}

std::string read_ini_value(const fs::path& file, const std::string& section,
                           const std::string& key, const std::string& fallback) {
    std::ifstream input(file);
    if (!input) return fallback;
    std::string line;
    std::string active_section;
    while (std::getline(input, line)) {
        line = trim(line);
        if (line.empty() || line[0] == '#' || line[0] == ';') continue;
        if (line.front() == '[' && line.back() == ']') {
            active_section = trim(line.substr(1, line.size() - 2));
            continue;
        }
        if (active_section != section) continue;
        const auto equals = line.find('=');
        if (equals == std::string::npos) continue;
        if (trim(line.substr(0, equals)) == key)
            return trim(line.substr(equals + 1));
    }
    return fallback;
}

unsigned int parse_modifiers(const std::string& value) {
    unsigned int result = 0;
    std::stringstream stream(value);
    std::string token;
    while (std::getline(stream, token, '+')) {
        token = trim(token);
        std::transform(token.begin(), token.end(), token.begin(),
                       [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
        if (token == "mod1" || token == "alt") result |= Mod1Mask;
        else if (token == "mod2") result |= Mod2Mask;
        else if (token == "mod3") result |= Mod3Mask;
        else if (token == "mod4" || token == "super" || token == "win") result |= Mod4Mask;
        else if (token == "mod5") result |= Mod5Mask;
        else if (token == "ctrl" || token == "control") result |= ControlMask;
        else if (token == "shift") result |= ShiftMask;
    }
    return result;
}


int x_error_handler(Display*, XErrorEvent* event) {
    if (event->error_code == BadAccess) {
        grab_failed = true;
    }

    return 0;
}


fs::path get_project_path() {
    // Resolve the actual daemon executable.
    std::vector<char> buffer(4096);

    ssize_t length = readlink(
        "/proc/self/exe",
        buffer.data(),
        buffer.size() - 1
    );

    if (length == -1) {
        throw std::runtime_error(
            "Cannot resolve daemon executable path."
        );
    }

    buffer[length] = '\0';

    fs::path executable(buffer.data());

    // Assumes the daemon binary is in the project root.
    return executable.parent_path();
}


bool launch_rubberducky(
    const fs::path& project_path
) {
    const fs::path python_path =
        project_path / ".venv/bin/python";

    const fs::path script_path =
        project_path / "src/ducky.py";

    if (!fs::exists(python_path)) {
        std::cerr << "Python environment not found: "
                  << python_path << std::endl;
        return false;
    }

    if (!fs::exists(script_path)) {
        std::cerr << "RubberDucky script not found: "
                  << script_path << std::endl;
        return false;
    }

    pid_t pid = fork();

    if (pid < 0) {
        std::cerr << "Fork failed: "
                  << std::strerror(errno) << std::endl;
        return false;
    }

    if (pid == 0) {
        // Child process.
        if (chdir(project_path.c_str()) != 0) {
            std::cerr << "Could not change project directory."
                      << std::endl;
            _exit(1);
        }

        std::string python = python_path.string();
        std::string script = script_path.string();

        char* const args[] = {
            python.data(),
            script.data(),
            nullptr
        };

        execv(python.c_str(), args);

        std::cerr << "Failed to launch Python: "
                  << std::strerror(errno) << std::endl;

        _exit(127);
    }

    // Parent waits for the pipeline to finish.
    // This prevents multiple simultaneous RubberDucky instances.
    int status = 0;

    while (waitpid(pid, &status, 0) == -1) {
        if (errno == EINTR) {
            continue;
        }

        std::cerr << "waitpid failed: "
                  << std::strerror(errno) << std::endl;
        return false;
    }

    if (WIFEXITED(status)) {
        int exit_code = WEXITSTATUS(status);

        if (exit_code != 0) {
            std::cerr << "RubberDucky exited with code: "
                      << exit_code << std::endl;
            return false;
        }

        return true;
    }

    if (WIFSIGNALED(status)) {
        std::cerr << "RubberDucky terminated by signal: "
                  << WTERMSIG(status) << std::endl;
    }

    return false;
}


int main() {
    Display* display = XOpenDisplay(nullptr);

    if (!display) {
        std::cerr << "Cannot open X11 display." << std::endl;
        return 1;
    }

    fs::path project_path;

    try {
        project_path = get_project_path();
    }
    catch (const std::exception& exc) {
        std::cerr << exc.what() << std::endl;
        XCloseDisplay(display);
        return 1;
    }

    std::cout << "Project: "
              << project_path << std::endl;

    Window root = DefaultRootWindow(display);

    const fs::path config_file = project_path / "rubberducky.ini";
    const std::string hotkey_name = read_ini_value(config_file, "hotkey", "key", "v");
    const std::string modifier_names = read_ini_value(config_file, "hotkey", "modifiers", "Mod4+Alt");
    const unsigned int modifiers = parse_modifiers(modifier_names);
    const KeySym hotkey_symbol = XStringToKeysym(hotkey_name.c_str());
    KeyCode hotkey_key = XKeysymToKeycode(display, hotkey_symbol);

    if (hotkey_symbol == NoSymbol || hotkey_key == 0 || modifiers == 0) {
        std::cerr << "Invalid hotkey in rubberducky.ini: "
                  << modifier_names << "+" << hotkey_name << std::endl;
        XCloseDisplay(display);
        return 1;
    }

    // Disable detectable key repeat when supported.
    Bool detectable_repeat = False;
    XkbSetDetectableAutoRepeat(
        display,
        True,
        &detectable_repeat
    );

    // Register an X11 error handler to detect hotkey conflicts.
    XSetErrorHandler(x_error_handler);

    // Support NumLock and CapsLock combinations.
    const std::vector<unsigned int> lock_masks = {
        0,
        Mod2Mask,
        LockMask,
        Mod2Mask | LockMask
    };

    for (unsigned int lock_mask : lock_masks) {
        XGrabKey(
            display,
            hotkey_key,
            modifiers | lock_mask,
            root,
            True,
            GrabModeAsync,
            GrabModeAsync
        );
    }

    XSync(display, False);

    if (grab_failed) {
        std::cerr << "Hotkey registration failed. "
                  << "Another application may own the configured hotkey."
                  << std::endl;

        XCloseDisplay(display);
        return 1;
    }

    XSelectInput(display, root, KeyPressMask);

    std::cout
        << "🦆 RubberDucky daemon active.\n"
        << "Listening for " << modifier_names << "+" << hotkey_name << "..."
        << std::endl;

    XEvent event;

    while (true) {
        XNextEvent(display, &event);

        if (event.type != KeyPress) {
            continue;
        }

        if (event.xkey.keycode != hotkey_key) {
            continue;
        }

        const unsigned int required = modifiers;

        if (
            (event.xkey.state & required)
            != required
        ) {
            continue;
        }

        std::cout
            << "\n[!] Hotkey detected! "
            << "Starting RubberDucky..."
            << std::endl;

        bool success = launch_rubberducky(project_path);

        if (success) {
            std::cout << "RubberDucky finished successfully."
                      << std::endl;
        } else {
            std::cerr << "RubberDucky encountered an error."
                      << std::endl;
        }

        std::cout << "Listening for hotkey..." << std::endl;
    }

    XCloseDisplay(display);
    return 0;
}

