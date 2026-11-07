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

namespace fs = std::filesystem;

bool grab_failed = false;

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

    const unsigned int modifiers = Mod4Mask | Mod1Mask;

    KeyCode v_key = XKeysymToKeycode(display, XK_v);

    if (v_key == 0) {
        std::cerr << "Could not resolve V keycode." << std::endl;
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
            v_key,
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
                  << "Another application may own Win + Alt + V."
                  << std::endl;

        XCloseDisplay(display);
        return 1;
    }

    XSelectInput(display, root, KeyPressMask);

    std::cout
        << "🦆 RubberDucky daemon active.\n"
        << "Listening for Win + Alt + V..."
        << std::endl;

    XEvent event;

    while (true) {
        XNextEvent(display, &event);

        if (event.type != KeyPress) {
            continue;
        }

        if (event.xkey.keycode != v_key) {
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

