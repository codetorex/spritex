# spritex
A simple tool for extracting sprites from full frames. Useful for AI projects. Made using Python 3, Kivy, pillow and numpy.


## Installation
To install, run ```install.sh``` which will create a symbolic link from "bin/spritex" to "/usr/local/bin" folder.

### Dependencies
* numpy==1.12.1
* Kivy>=1.10.0
* pillow>=2.1.0

You can install dependencies via pip: 

```pip install -r requirements.txt --upgrade```

#### Arch Linux
You can install dependencies via pacman.

```sudo pacman -S python-pillow python-kivy python-numpy```

## Usage
You can open image files through ```spritex path.png```. If you use SDL2 backend you can drag and drop image files on to application window.

After a region selected roughly, it is possible to fine tune by arrow keys.

### Keyboard shortcuts

* Without any modifiers arrow keys will move selection around by 1 px.
* With Ctrl modifier selection will grow on bottom and right side by 1 px.
* With Alt modifier selection will grow on top and left side by 1 px.
* With shift modifier all operations will do 5px.

### Operations
* Create sprite: will create an image from selection into same folder of source image. 
    * *Useful at creating training data for ANN classifiers.*
* Find unique colors: will extract unique colors of the selection relative to rest of the image. Output will be (unique color count)x1 image and will be saved into same folder with source. 
    * *Useful at locating simple objects that represented by unique colors from screen frame.* 
* Highlight unique colors: will extract an image with unique colors only.
    * *Useful at locating simple objects that represented by unique colors at unique positions from screen frame.*

### Screenshots

![Screenshot](/../screenshots/screenshot.png?raw=true "Screenshot")