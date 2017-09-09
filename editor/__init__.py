import io
import time
from pathlib import Path
from typing import Generic, Callable, List

import numpy as np
import sys
from PIL import Image as PILImage
from PIL import ImageDraw
from kivy.app import App
from kivy.core.clipboard import Clipboard
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.graphics.context_instructions import Color
from kivy.graphics.instructions import InstructionGroup
from kivy.graphics.vertex_instructions import Line, Rectangle
from kivy.properties import ObjectProperty, NumericProperty, BooleanProperty, Clock, partial, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.stacklayout import StackLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.widget import Widget


class SpriteEditorApp(App):
    def __init__(self):
        super(SpriteEditorApp, self).__init__()
        self.canvas: 'SpriteEditorWidget' = None

    def build(self):
        self.canvas = SpriteEditorWidget()
        return self.canvas


class SpriteEditorInfoLabel(Label):
    name = StringProperty()
    val_format = StringProperty()

    def __init__(self, **kwargs):
        super(SpriteEditorInfoLabel, self).__init__(**kwargs)

    def set_value(self, value):
        formatted = self.val_format % value
        self.text = f"{self.name}: {formatted}"


class SpriteEditorWidget(Widget):
    image: PILImage = ObjectProperty(None)
    core_image: CoreImage = ObjectProperty(None)
    image_path: str = StringProperty(None)

    def _create_info_label(self, name, val_format="%i"):
        label = SpriteEditorInfoLabel(halign="left", text_size=(200, 32), size=(200, 20), size_hint=(1, None),
                                      padding=[8, 8])
        label.name = name
        label.val_format = val_format
        self.info_stack.add_widget(label)
        return label

    def _create_tool_button(self, name, pressed: Callable):
        result = Button(text=name, size=(200, 50), size_hint=(1, None))
        result.bind(on_press=pressed)
        self.tool_stack.add_widget(result)
        return result

    def __init__(self, **kwargs):
        super(SpriteEditorWidget, self).__init__(**kwargs)
        # self.images = dict()

        self.root = BoxLayout(orientation='horizontal')
        # self.root = FloatLayout(size=(Window.width, Window.height))
        # self.grid = GridLayout(cols=8)

        self.add_widget(self.root)

        self.viewer = SpriteEditorViewer(owner=self, size_hint=(.7, 1))
        self.viewer.padding = [4, 4]
        self.root.add_widget(self.viewer)

        self.toolbox = BoxLayout(orientation='vertical', size=(200, 50), size_hint=(None, 1))
        self.root.add_widget(self.toolbox)

        tool_stack = StackLayout(size=(200, 50), size_hint=(None, 0.7))
        tool_stack.orientation = "tb-lr"
        tool_stack.padding = [4, 4]
        self.toolbox.add_widget(tool_stack)
        self.tool_stack = tool_stack

        # self._create_tool_button('Load Image', self.load_image_press)
        self._create_tool_button('Toggle Grid', self.toggle_grid_press)
        self.select_button = self._create_tool_button('Select Region', self.select_press)
        self._create_tool_button('Copy Region to Clipboard', self.copy_region_press)
        self._create_tool_button('Create Sprite', self.create_sprite_press)
        self._create_tool_button('Find Unique Colors', self.find_unique_press)
        self._create_tool_button('Highlight Unique Colors', self.highlight_unique_press)

        info_stack = StackLayout(size=(200, 50), size_hint=(None, 0.3))
        info_stack.orientation = "tb-lr"
        info_stack.padding = [4, 4]
        self.info_stack = info_stack

        self.x_label = self._create_info_label("x")
        self.y_label = self._create_info_label("y")

        self.sel_x_label = self._create_info_label("sel x")
        self.sel_y_label = self._create_info_label("sel y")
        self.sel_width_label = self._create_info_label("sel width")
        self.sel_height_label = self._create_info_label("sel height")

        self.toolbox.add_widget(info_stack)

        Window.bind(on_resize=self.on_window_resize)
        Window.clearcolor = (0.136, 0.191, 0.25, 1)
        Window.bind(on_dropfile=self._on_drop_file)
        self.root.size = (Window.width, Window.height)

        if len(sys.argv) > 1:
            self.load_image(sys.argv[1])

    def _on_drop_file(self, window, file_path):
        print(file_path)
        self.load_image(file_path)

    def copy_region_press(self, *args):
        region = self.viewer.selection
        Clipboard.copy(f"\"REGION\": ({region.sel_y}, {region.sel_x}," +
                       f" {region.sel_y + region.sel_height}, {region.sel_x + region.sel_width})")

    @staticmethod
    def date_for_filename():
        return time.strftime("%Y%m%d%H%M%S", time.localtime())

    def highlight_unique_press(self, *args):
        sprite = np.array(self.get_selection_image()).tolist()
        unique = self.find_unique_colors()

        result = []
        for rows in sprite:
            row = []
            for pixel in rows:
                if pixel in unique:
                    row.append(pixel)
                else:
                    row.append([0, 0, 0])
            result.append(row)

        result = np.array(result)
        result_image = PILImage.fromarray(result.astype('uint8'), "RGB")
        self.save_image("highlight", result_image)

    def get_selection_region(self):
        region = self.viewer.selection

        selection = (region.sel_x - 1, region.sel_y - 1,
                     region.sel_x + region.sel_width - 1,
                     region.sel_y + region.sel_height - 1)
        return selection

    def get_selection_image(self) -> PILImage:
        image: PILImage = self.image
        selection = self.get_selection_region()
        sprite = image.crop(selection)
        return sprite

    def find_unique_colors(self) -> List[List[int]]:
        selection = self.get_selection_region()
        sprite = self.get_selection_image()

        image: PILImage = self.image.copy()
        draw = ImageDraw.Draw(image)
        draw.rectangle(selection, fill=0)
        del draw

        rest_pixels = np.array(image)
        sprite_pixels = np.array(sprite)

        rest_colors = np.unique(rest_pixels.reshape(-1, 3), axis=0).tolist()
        rest_colors = [item for item in rest_colors if item is not [0, 0, 0]]
        sprite_colors = np.unique(sprite_pixels.reshape(-1, 3), axis=0).tolist()

        unique_colors = [item for item in sprite_colors if item not in rest_colors]

        if len(unique_colors) == 0:
            print("No unique colors found")
            return

        unique_colors.sort(reverse=True)
        return unique_colors

    def save_image(self, name, image):
        p = Path(self.image_path)
        p = p.parents[0] / f"{name}_{self.date_for_filename()}.png"
        print (p)
        image.save(p)
        print("File written to:", p)

    def find_unique_press(self, *args):
        unique_colors = self.find_unique_colors()
        unique_colors = np.array([unique_colors])
        print(unique_colors)
        print(unique_colors.shape)
        unique_color_image = PILImage.fromarray(unique_colors.astype('uint8'), "RGB")

        self.save_image("unique", unique_color_image)

    def create_sprite_press(self, *args):
        sprite = self.get_selection_image()
        self.save_image("sprite", sprite)

    def toggle_grid_press(self, *args):
        self.viewer.toggle_grid()

    def on_image_path(self, *args):
        self.image = PILImage.open(self.image_path)  # CoreImage(path, keep_data=True)

    def load_image(self, path):
        self.image_path = path

    def on_image(self, sender, image: PILImage):
        print("Image set")

        image = self.image.convert("RGB")
        image_file = io.BytesIO()

        image.save(image_file, "png")
        image_file.seek(0)

        self.core_image = CoreImage(image_file, ext="png")
        self.viewer.set_texture(self.core_image.texture)

    def select_press(self, *args):
        self.viewer.tool = RegionTool()

    def on_window_resize(self, window, width, height):
        self.root.size = (width, height)


class Tool:
    def begin(self, editor: 'SpriteEditorViewer'):
        pass

    def end(self, editor: 'SpriteEditorViewer'):
        pass

    def down(self, editor: 'SpriteEditorViewer', touch):
        pass

    def up(self, editor: 'SpriteEditorViewer', touch):
        pass

    def move(self, editor: 'SpriteEditorViewer', touch):
        pass


class ZoomTool(Tool):
    def down(self, editor: 'SpriteEditorViewer', touch):
        local_pos = editor.image.to_local(touch.x, touch.y, relative=True)
        if touch.button == "scrolldown":
            editor.set_scale(editor.zoom_ratio, local_pos)
            return True
        elif touch.button == "scrollup":
            editor.set_scale(1.0 / editor.zoom_ratio, local_pos)
            return True


class PanZoomTool(ZoomTool):
    def move(self, editor: 'SpriteEditorViewer', touch):
        editor.image.x += touch.dx
        editor.image.y += touch.dy
        super().move(editor, touch)


class RegionTool(Tool):
    def begin(self, editor: 'SpriteEditorViewer'):
        editor.selection.visible = False
        editor.selection.sel_x = 0
        editor.selection.sel_y = 0
        editor.selection.sel_width = 0
        editor.selection.sel_height = 0
        editor.owner.select_button.background_color = [0, 1, 0, 1]

    def end(self, editor: 'SpriteEditorViewer'):
        editor.owner.select_button.background_color = [1, 1, 1, 1]

    def down(self, editor: 'SpriteEditorViewer', touch):
        local_pos = editor.window_pos_to_image((touch.x, touch.y))
        editor.selection.sel_x = local_pos[0]
        editor.selection.sel_y = local_pos[1]
        editor.selection.visible = True

    def move(self, editor: 'SpriteEditorViewer', touch):
        local_pos = editor.window_pos_to_image((touch.x, touch.y))
        editor.selection.sel_width = (local_pos[0] - editor.selection.sel_x) + 1
        editor.selection.sel_height = (local_pos[1] - editor.selection.sel_y) + 1

    def up(self, editor: 'SpriteEditorViewer', touch):
        local_pos = editor.window_pos_to_image((touch.x, touch.y))
        editor.selection.sel_width = (local_pos[0] - editor.selection.sel_x) + 1
        editor.selection.sel_height = (local_pos[1] - editor.selection.sel_y) + 1
        editor.tool = PanZoomTool()


class RegionSelection(Widget):
    sel_x = NumericProperty(0.0)
    sel_y = NumericProperty(0.0)
    sel_width = NumericProperty(0.0)
    sel_height = NumericProperty(0.0)
    visible = BooleanProperty(False)
    rect = ObjectProperty(None)

    def __init__(self, viewer: 'SpriteEditorViewer' = None, **kwargs):
        super(RegionSelection, self).__init__(**kwargs)
        self.viewer = viewer
        self.bind(sel_x=self.update, sel_y=self.update, sel_width=self.update, sel_height=self.update)
        self.viewer.image.bind(size=self.update, pos=self.update)
        self.viewer.bind(xscale=self.update, yscale=self.update)
        self.bind(visible=self.redraw)

        self._keyboard = Window.request_keyboard(
            self._keyboard_closed, self, 'text')
        if self._keyboard.widget:
            pass
        self._keyboard.bind(on_key_down=self._on_keyboard_down)

    def _keyboard_closed(self):
        print('My keyboard have been closed!')
        self._keyboard.unbind(on_key_down=self._on_keyboard_down)
        self._keyboard = None

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        amount = 1
        if "shift" in modifiers:
            amount = 5

        if "alt" in modifiers:
            if keycode[1] == "up":
                self.sel_height += amount
                self.sel_y -= amount
                return True
            elif keycode[1] == "down":
                self.sel_height -= amount
                self.sel_y += amount
                return True
            elif keycode[1] == "left":
                self.sel_width += amount
                self.sel_x -= amount
                return True
            elif keycode[1] == "right":
                self.sel_width -= amount
                self.sel_x += amount
                return True
        elif "ctrl" in modifiers:
            if keycode[1] == "up":
                self.sel_height -= amount
                return True
            elif keycode[1] == "down":
                self.sel_height += amount
                return True
            elif keycode[1] == "left":
                self.sel_width -= amount
                return True
            elif keycode[1] == "right":
                self.sel_width += amount
                return True
        else:
            if keycode[1] == "up":
                self.sel_y -= amount
                return True
            elif keycode[1] == "down":
                self.sel_y += amount
                return True
            elif keycode[1] == "left":
                self.sel_x -= amount
                return True
            elif keycode[1] == "right":
                self.sel_x += amount
                return True

        return False

    def update(self, *args):
        if self.rect is None:
            self.redraw()
            return

        self.rect.pos = self.viewer.image_pos_to_window((self.sel_x - 1, self.sel_y + self.sel_height - 1))
        self.rect.size = self.viewer.image_size_to_window(self.sel_width, self.sel_height)

        self.viewer.owner.sel_x_label.set_value(self.sel_x)
        self.viewer.owner.sel_y_label.set_value(self.sel_y)
        self.viewer.owner.sel_width_label.set_value(self.sel_width)
        self.viewer.owner.sel_height_label.set_value(self.sel_height)

    def redraw(self, *args):
        self.canvas.clear()
        if not self.visible:
            return

        with self.canvas:
            Color(0.5, 1, 0.5, 0.3)
            self.rect = Rectangle()
        self.update()


class SpriteEditorViewer(FloatLayout, StencilView):
    image = ObjectProperty(None)
    selection = ObjectProperty(None)
    zoom_ratio = NumericProperty(1.04)
    xscale = NumericProperty(1.0)
    yscale = NumericProperty(1.0)

    def __init__(self, owner=None, **kwargs):
        super(SpriteEditorViewer, self).__init__(**kwargs)

        self.image = SpriteEditorImage(allow_stretch=True, nocache=True, size_hint=(None, None))
        self.add_widget(self.image)
        self.owner: 'SpriteEditorWidget' = owner

        self.grid = SpriteEditorGrid(owner=self.image, size_hint=(None, None))
        self.add_widget(self.grid)
        self._tool: Generic[Tool] = None
        self.tool = PanZoomTool()

        self.selection = RegionSelection(viewer=self)
        self.add_widget(self.selection)

        Clock.schedule_interval(partial(self.update_info_callback), 0.05)

    @property
    def tool(self):
        return self._tool

    @tool.setter
    def tool(self, value):
        if self._tool is not None:
            self._tool.end(self)
        self._tool = value
        self._tool.begin(self)

    def image_size_to_window(self, width, height):
        return width * self.xscale, height * self.yscale

    def image_pos_to_window(self, pos):
        local_pos = list(pos)
        local_pos[0] *= self.xscale
        local_pos[1] *= self.yscale
        local_pos[1] = self.image.height - local_pos[1]
        win_pos = self.image.to_window(local_pos[0], local_pos[1], initial=False, relative=True)
        return list(win_pos)

    def window_pos_to_image(self, pos):
        local_pos = list(self.image.to_local(pos[0], pos[1], relative=True))

        local_pos[1] = self.image.size[1] - local_pos[1]

        local_pos[0] /= self.xscale
        local_pos[1] /= self.yscale

        if local_pos[0] < 0:
            local_pos[0] = 0

        if local_pos[1] < 0:
            local_pos[1] = 0

        if local_pos[0] >= self.image.texture.size[0]:
            local_pos[0] = self.image.texture.size[0] - 1

        if local_pos[1] >= self.image.texture.size[1]:
            local_pos[1] = self.image.texture.size[1] - 1

        local_pos[0] = int(local_pos[0]) + 1
        local_pos[1] = int(local_pos[1]) + 1
        return local_pos

    def get_mouse_image_pos(self):
        pos = Window.mouse_pos
        local_pos = self.window_pos_to_image(pos)
        return local_pos

    def update_info_callback(self, dt):
        if self.image.texture is None:
            return

        local_pos = self.get_mouse_image_pos()
        self.owner.x_label.set_value(local_pos[0])
        self.owner.y_label.set_value(local_pos[1])

    def toggle_grid(self, value=None):
        if value is None:
            self.grid.visible = not self.grid.visible
        else:
            self.grid.visible = value
        pass

    def set_scale(self, value, local_pos):
        self.image.size = (self.image.size[0] * value, self.image.size[1] * value)

        self.image.x -= local_pos[0] * (value - 1.0)
        self.image.y -= local_pos[1] * (value - 1.0)

        self.xscale = self.image.size[0] / self.image.texture.size[0]
        self.yscale = self.image.size[1] / self.image.texture.size[1]

    def set_texture(self, texture):
        self.image.texture = texture
        self.reset_zoom()

    def reset_zoom(self):
        self.image.size = self.image.texture.size
        self.image.pos = (0.0, 0.0)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super(SpriteEditorViewer, self).on_touch_down(touch)

        self._tool.down(self, touch)
        return super(SpriteEditorViewer, self).on_touch_down(touch)

    def on_touch_move(self, touch):
        if not self.collide_point(*touch.pos):
            return super(SpriteEditorViewer, self).on_touch_move(touch)

        self._tool.move(self, touch)
        return super(SpriteEditorViewer, self).on_touch_move(touch)

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return super(SpriteEditorViewer, self).on_touch_up(touch)

        self._tool.up(self, touch)
        return super(SpriteEditorViewer, self).on_touch_up(touch)


class SpriteEditorGrid(Widget):
    visible = BooleanProperty(False)

    def __init__(self, owner: 'SpriteEditorImage' = None, **kwargs):
        super(SpriteEditorGrid, self).__init__(**kwargs)
        self.owner = owner
        self.owner.bind(size=self.redraw, pos=self.redraw)
        self.bind(visible=self.redraw)

    def update(self, *args):
        self.pos = self.owner.pos
        self.size = self.owner.size
        self.redraw()

    def redraw(self, *args):
        # self.update()
        self.canvas.clear()
        if not self.visible:
            return

        self.pos = self.owner.pos
        self.size = self.owner.size

        width = self.owner.texture.size[0]
        height = self.owner.texture.size[1]

        h_stride = self.width / width
        v_stride = self.height / height

        grid = InstructionGroup()

        grid.add(Color(1, 1, 1))
        for y in range(0, height):
            grid.add(Line(points=[self.x + 0, self.y + y * v_stride, self.x + self.width, self.y + y * v_stride]))
        for x in range(0, width):
            grid.add(Line(points=[self.x + x * h_stride, self.y + 0, self.x + x * h_stride, self.y + self.height]))

        self.canvas.add(grid)


class SpriteEditorImage(Image):
    def __init__(self, **kwargs):
        super(SpriteEditorImage, self).__init__(**kwargs)
        self.bind(texture=self.update_texture_filters)

    def update_texture_filters(self, *args):
        self.texture.min_filter = 'nearest'
        self.texture.mag_filter = 'nearest'
