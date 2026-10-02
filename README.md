# QFP

QFP is a desktop projector-mapping application. It captures a monitor or
window, lets you position the captured image by moving its four corners, and
renders the result to another display.

This project is provided as-is and is still experimental. Test it with your
hardware and applications before relying on it for a live production setup.

## Features

- Capture a monitor or a visible application window.
- Map each source to a quadrilateral using draggable corner pins.
- Move and resize layers independently.
- Render the composition to a selected display in fullscreen mode.
- Run the preview and projector output at the same time.

## Requirements

- Python 3.8 or newer.
- A desktop environment with an available display.
- On Windows, the application uses native window APIs for window capture.
- On other platforms, window enumeration and capture depend on the platform's
  display-server permissions and support. Monitor capture is the more portable
  option.

Install the Python dependencies with:

```sh
python -m pip install PySide6 opencv-python numpy mss
```

On non-Windows systems, install `pygetwindow` as well if you want to use
window enumeration:

```sh
python -m pip install pygetwindow
```

For repeatable environments, use a virtual environment before installing
dependencies.

## Run from source

From the project directory:

```sh
python QFP_main.py
```

To use the application:

1. Select the display that should receive the projector output.
2. Add a monitor or application window as a source.
3. Select a layer in the list or preview.
4. Drag its corner pins to align the image with the physical surface.
5. Start projector output when the mapping is ready.

### Preview controls

- Click a layer to select it.
- Drag a corner pin to move one corner.
- Hold **Shift** while dragging a layer to move the whole layer.
- Hold **Ctrl** for fine mouse movement.
- Use the arrow keys to nudge the selected layer or active corner.
- Hold **Shift** with an arrow key for a larger nudge.
- Hold **Ctrl** with an arrow key for a finer nudge.
- Press **1** through **4** to select a corner.
- Press **Esc** to deselect; press **Esc** on the projector window to close it.

## Screen-capture and privacy notice

QFP captures pixels from the monitors and windows that you select and displays
them in the preview or on the chosen projector display. Captured content is
processed locally by the application; this project does not intentionally
upload it to a server. Do not capture confidential or sensitive material
unless you understand the risks of displaying it on another screen.

Operating-system permissions, protected windows, minimized windows, and
hardware-accelerated applications may prevent capture or produce a black or
incomplete image. The application does not bypass those protections.

## Building a Windows executable

The repository includes a PyInstaller build script. Install PyInstaller and
run:

```sh
python -m pip install pyinstaller
python build.py
```

The generated executable is placed in the `dist` directory. Build artifacts
are intended to be tested before distribution; they should generally be
attached to a GitHub Release rather than committed to the source repository.

## Building a Linux executable:

1. Open a terminal
2. Fork the repo
3. Open a terminal
4. Ask Claude to add Linux support
5. Open a terminal

## Known limitations

- Capture behavior varies by operating system, window manager, permissions,
  and application.
- Some applications, including certain browsers and protected or
  hardware-accelerated windows, may not capture correctly.
- Projector output and window capture have primarily been developed and tested
  on Windows.
- QFP does not save or restore mapping projects yet.

## License

QFP is distributed under the MIT License. See
[LICENSE.txt](LICENSE.txt) for the full license text.

QFP uses third-party libraries. Review and comply with the licenses of
[PySide6/Qt](https://www.qt.io/licensing/),
[OpenCV](https://opencv.org/license/),
[NumPy](https://numpy.org/doc/stable/license.html),
[python-mss](https://github.com/BoboTiG/python-mss/blob/develop/LICENSE.txt),
and any optional platform-specific dependencies before redistributing a
packaged build.
