#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <iostream>
#include <cstdlib>
#include <string>

int main() {
    Display* display = XOpenDisplay(NULL);
    if (display == NULL) {
        std::cerr << "Cannot open X11 display" << std::endl;
        return 1;
    }

    Window root = DefaultRootWindow(display);
    unsigned int modifiers = Mod4Mask | Mod1Mask;
    KeyCode v_key = XKeysymToKeycode(display, XK_v);

    XGrabKey(display, v_key, modifiers, root, True, GrabModeAsync, GrabModeAsync);
    XGrabKey(display, v_key, modifiers | Mod2Mask, root, True, GrabModeAsync, GrabModeAsync);
    XGrabKey(display, v_key, modifiers | LockMask, root, True, GrabModeAsync, GrabModeAsync);
    XGrabKey(display, v_key, modifiers | Mod2Mask | LockMask, root, True, GrabModeAsync, GrabModeAsync);

    XSelectInput(display, root, KeyPressMask);
    std::cout << "🦆 RubberDucky Daemon active. Listening for Win + Alt + V..." << std::endl;

    // Dynamically resolve the project path relative to HOME
    const char* homeDir = getenv("HOME");
    std::string projectPath = std::string(homeDir) + "/Desktop/Projects/RubberDucky";
    std::string command = "cd " + projectPath + " && " + projectPath + "/.venv/bin/python src/ducky.py";

    XEvent event;
    while (true) {
        XNextEvent(display, &event);
        if (event.type == KeyPress) {
            if (event.xkey.keycode == v_key) {
                std::cout << "\n[!] Hotkey detected! Waking up RubberDucky..." << std::endl;
                
                int result = system(command.c_str());
                if (result != 0) {
                    std::cerr << "Pipeline error code: " << result << std::endl;
                }
                
                std::cout << "\n🦆 RubberDucky returned to sleep. Listening..." << std::endl;
            }
        }
    }

    XCloseDisplay(display);
    return 0;
}
