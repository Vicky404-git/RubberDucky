#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <iostream>
#include <cstdlib>

int main() {
    Display* display = XOpenDisplay(NULL);
    if (display == NULL) {
        std::cerr << "Cannot open X11 display" << std::endl;
        return 1;
    }

    Window root = DefaultRootWindow(display);

    // Mod4Mask = Super/Win Key
    // Mod1Mask = Alt Key
    unsigned int modifiers = Mod4Mask | Mod1Mask;
    KeyCode v_key = XKeysymToKeycode(display, XK_v);

    // Grab the key combinations (including NumLock and CapsLock states)
    XGrabKey(display, v_key, modifiers, root, True, GrabModeAsync, GrabModeAsync);
    XGrabKey(display, v_key, modifiers | Mod2Mask, root, True, GrabModeAsync, GrabModeAsync);
    XGrabKey(display, v_key, modifiers | LockMask, root, True, GrabModeAsync, GrabModeAsync);
    XGrabKey(display, v_key, modifiers | Mod2Mask | LockMask, root, True, GrabModeAsync, GrabModeAsync);

    XSelectInput(display, root, KeyPressMask);

    std::cout << "🦆 RubberDucky Daemon active. Listening for Win + Alt + V..." << std::endl;

    XEvent event;
    while (true) {
        XNextEvent(display, &event);
        if (event.type == KeyPress) {
            if (event.xkey.keycode == v_key) {
                std::cout << "\n[!] Hotkey detected! Waking up RubberDucky..." << std::endl;
                
                // IMPORTANT: Ensure this path matches exactly where your project is
                int result = system("cd /home/vicky-404/Desktop/Projects/RubberDucky && /home/vicky-404/Desktop/Projects/RubberDucky/.venv/bin/python src/ducky.py");
                
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
