import io
import time
import os
from pathlib import Path
from typing import Generic, Callable, List, Optional

import numpy as np
import sys
from PIL import Image as PILImage, ImageChops
from PIL import ImageDraw
from kivy.app import App
from kivy.base import EventLoop
from kivy.core.clipboard import Clipboard
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.graphics.context_instructions import Color
from kivy.graphics.instructions import InstructionGroup
from kivy.graphics.vertex_instructions import Line, Rectangle
from kivy.metrics import dp
from kivy.properties import ObjectProperty, NumericProperty, BooleanProperty, Clock, partial, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.stacklayout import StackLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.widget import Widget


def execute():
    SpriteEditorApp().run()


class SpriteEditorApp(App):
    def __init__(self):
        super(SpriteEditorApp, self).__init__()
        self.canvas: 'SpriteEditorWidget' = None

    def build(self):
        self.canvas = SpriteEditorWidget()
        self.title = "Sprite Extractor"
        return self.canvas


class SpriteEditorInfoLabel(Label):
    name = StringProperty()
    val_format = StringProperty()

    def __init__(self, **kwargs):
        super(SpriteEditorInfoLabel, self).__init__(**kwargs)

    def set_value(self, value):
        formatted = self.val_format % value
        self.markup = True
        self.text = f"[b]{self.name}:[/b] {formatted}"


class SpriteEditorProgress(ProgressBar):
    def __init__(self, **kwargs):
        super(SpriteEditorProgress, self).__init__(**kwargs)
        self.last_update = time.time()
        target_fps = 60.0
        self.frame_time = 1.0 / target_fps
        self.opacity = 0

    def update(self, value):
        self.value = value
        if 0.0 < value < 100.0:
            self.opacity = 1.0
        else:
            self.opacity = 0.0

        if time.time() - self.last_update > self.frame_time:
            EventLoop.idle()
            self.last_update = time.time()

    def step(self, value):
        self.update(self.value + value)

    def partial_step(self, done, total, final):
        step = (done / total) * final
        self.step(step)


class SpriteEditorWidget(Widget):
    image: PILImage = ObjectProperty(None)
    core_image: CoreImage = ObjectProperty(None)
    image_path: str = StringProperty(None)
    button_height = dp(35)
    label_height = dp(20)
    progress: SpriteEditorProgress = ObjectProperty(None)

    def show_popup(self, text):
        popup = Popup(title="Sprite Extractor", content=Label(text=text, markup=True), size_hint=(0.6, 0.3))
        popup.open()

    def _create_info_label(self, name, val_format="%i"):
        label = SpriteEditorInfoLabel(halign="left", text_size=(200, dp(32)), size=(200, self.label_height),
                                      size_hint=(1, None),
                                      padding=[8, 8])
        label.name = name
        label.val_format = val_format
        self.tool_stack.add_widget(label)
        return label

    def _create_tool_button(self, name, pressed: Callable):
        result = Button(text=name, size=(200, self.button_height), size_hint=(1, None))
        result.bind(on_press=pressed)
        self.tool_stack.add_widget(result)
        return result

    def _create_tool_label(self, name):
        result = Label(halign="left", text_size=(200, dp(32)), size=(200, self.label_height), markup=True,
                       size_hint=(1, None), padding=[8, 8])
        result.text = "[b]" + name + "[/b]"
        self.tool_stack.add_widget(result)
        return result

    def _toggle_press(self, button, *args):
        button.sp_toggle = not button.sp_toggle
        if button.sp_toggle:
            button.background_color = [0, 1, 0, 1]
            button.sp_event(button, True)
        else:
            button.background_color = [1, 1, 1, 1]
            button.sp_event(button, False)

    def _create_toggle_button(self, name, pressed: Callable):
        result = Button(text=name, size=(200, self.button_height), size_hint=(1, None))
        result.sp_toggle = False
        result.sp_event = pressed
        result.bind(on_press=self._toggle_press)
        self.tool_stack.add_widget(result)
        return result

    def _on_overlay_update(self, *args):
        if self.overlay_updater is not None:
            self.overlay_updater()

    def __init__(self, **kwargs):
        super(SpriteEditorWidget, self).__init__(**kwargs)
        self.root = BoxLayout(orientation='horizontal')
        self.add_widget(self.root)

        self.viewer = SpriteEditorViewer(owner=self, size_hint=(.7, 1))

        self.progress = SpriteEditorProgress(max=100, pos_hint={'x': 0, 'y': 0.98}, size=(100, dp(10)),
                                             size_hint=(1, None))
        self.viewer.add_widget(self.progress)

        self.viewer.padding = [4, 4]
        self.root.add_widget(self.viewer)

        tool_stack = StackLayout(size=(dp(200), 50), size_hint=(None, 1))
        tool_stack.orientation = "tb-lr"
        tool_stack.padding = [4, 4]
        tool_stack.spacing = 4
        self.root.add_widget(tool_stack)
        self.tool_stack = tool_stack

        self._create_toggle_button('Toggle Grid', self.toggle_grid_press)
        self.select_button = self._create_tool_button('Select Region', self.select_press)

        self._create_tool_button('Copy Region to Clipboard', self.copy_region_press)

        self._create_tool_label("Extract:")
        self._create_tool_button('Sprite', self.create_sprite_press)
        self._create_tool_button('Unique Colors', self.find_unique_press)
        self._create_tool_button('Unique Sprite', self.highlight_unique_press)
        self._create_tool_button('Transparent Sprite', self.extract_transparent_press)

        self._create_tool_label("Overlay:")
        self._create_toggle_button('Unique Colors', self.overlay_unique_press)
        self._create_toggle_button('Transparent Sprite', self.overlay_transparent_press)

        self.overlay_updater: Optional[Callable] = None

        self._create_tool_label("Region Info:")
        self.x_label = self._create_info_label("x")
        self.y_label = self._create_info_label("y")

        self.sel_x_label = self._create_info_label("sel x")
        self.sel_y_label = self._create_info_label("sel y")
        self.sel_width_label = self._create_info_label("sel width")
        self.sel_height_label = self._create_info_label("sel height")

        self.viewer.selection.bind(on_update=self._on_overlay_update)

        Window.bind(on_resize=self.on_window_resize)
        Window.clearcolor = (0.136, 0.191, 0.25, 1)
        Window.bind(on_dropfile=self._on_drop_file)
        self.root.size = (Window.width, Window.height)

        if len(sys.argv) > 1:
            self.load_image(sys.argv[1])

    def _on_drop_file(self, window, file_path):
        p = file_path.decode("utf-8")
        print(p)
        self.load_image(p)

    def copy_region_press(self, *args):
        region = self.viewer.selection
        text = f"\"REGION\": ({int(region.sel_y)}, {int(region.sel_x)}, {int(region.sel_y + region.sel_height)}, {int(region.sel_x + region.sel_width)})"
        Clipboard.copy(text)
        self.show_popup(f"Copied to clipboard:\n[b]{text}[/b]")

    @staticmethod
    def date_for_filename():
        return time.strftime("%Y%m%d%H%M%S", time.localtime())

    @property
    def is_region_selected(self):
        return self.viewer.selection.sel_width * self.viewer.selection.sel_height > 0.1

    def overlay_update_transparent_extractor(self):
        if not self.is_region_selected:
            return
        extracted = self.extract_transparent_black()
        self.viewer.selection.overlay = self.pil_to_core(extracted)

    def overlay_update_highlight_unique(self):
        if not self.is_region_selected:
            return
        extracted = self.highlight_unique()
        if extracted is None:
            self.viewer.selection.overlay = None
        else:
            self.viewer.selection.overlay = self.pil_to_core(extracted)

    def overlay_transparent_press(self, button, enabled, *args):
        if enabled:
            self.overlay_updater = self.overlay_update_transparent_extractor
            self.overlay_update_transparent_extractor()
        else:
            self.overlay_updater = None
            self.viewer.selection.overlay = None

    def overlay_unique_press(self, button, enabled, *args):
        if enabled:
            self.overlay_updater = self.overlay_update_highlight_unique
            self.overlay_update_highlight_unique()
        else:
            self.overlay_updater = None
            self.viewer.selection.overlay = None

    def extract_transparent_black(self):
        point_table = ([0] + ([255] * 255))

        def diff_image(a, b):
            diff = ImageChops.difference(a, b)
            diff = diff.convert('L')
            diff = diff.point(point_table)
            diff = ImageChops.invert(diff)
            new = diff.convert('RGB')
            new.paste(b, mask=diff)
            return new

        self.progress.update(0.1)

        p = Path(self.image_path)
        p = p.parents[0]
        sections = []
        for root, dirs, files in os.walk(p):
            for file in files:
                if not file.endswith(".png"):
                    continue

                image = PILImage.open(root + "/" + file)
                section = self.get_selection_image(image)
                sections.append(section.convert('RGB'))
                self.progress.partial_step(1, len(files), 40)

        result = sections.pop()
        for section in sections:
            result = diff_image(result, section)
            self.progress.partial_step(1, len(sections), 60)
        self.progress.update(100)
        return result

    def extract_transparent(self):
        point_table = ([0] + ([255] * 255))
        p = Path(self.image_path)
        p = p.parents[0]
        sections = []
        for root, dirs, files in os.walk(p):
            for file in files:

                if not file.endswith(".png"):
                    continue

                image = PILImage.open(file)
                section = self.get_selection_image(image)
                sections.append(np.array(section.convert('RGBA')))

        result = np.array(sections.pop()).tolist()
        for section in sections:
            for y, row in enumerate(result):
                for x, pixel in enumerate(row):
                    if np.all(pixel == section[y][x]):
                        continue
                    else:
                        pixel[3] = 0

        result = np.array(result)
        result_image = PILImage.fromarray(result.astype('uint8'), "RGBA")
        return result_image

    def check_region_selected(self):
        if not self.is_region_selected:
            self.show_popup("No region selected")
            return False
        return True

    def extract_transparent_press(self, *args):
        if not self.check_region_selected():
            return
        self.save_image("../extracted", self.extract_transparent())

    def highlight_unique(self):
        self.progress.update(0.1)
        sprite = np.array(self.get_selection_image()).tolist()
        self.progress.update(10.0)
        unique = self.find_unique_colors()
        if len(unique) == 0:
            self.progress.update(100)
            return None
        self.progress.update(20.0)

        result = []
        for rows in sprite:
            row = []
            for pixel in rows:
                if pixel in unique:
                    row.append([pixel[0], pixel[1], pixel[2], 255])
                else:
                    row.append([0, 0, 0, 0])
            result.append(row)
            self.progress.partial_step(1, len(sprite), 65.0)

        result = np.array(result)
        result_image = PILImage.fromarray(result.astype('uint8'), "RGBA")
        self.progress.update(100)
        return result_image

    def highlight_unique_press(self, *args):
        if not self.check_region_selected():
            return
        image = self.highlight_unique()
        if image == None:
            self.show_popup("No unique colors found")
        self.save_image("highlight", self.highlight_unique())

    def get_selection_region(self):
        region = self.viewer.selection

        selection = (region.sel_x, region.sel_y,
                     region.sel_x + region.sel_width,
                     region.sel_y + region.sel_height)
        return selection

    def get_selection_image(self, custom_image=None) -> PILImage:
        if custom_image is None:
            image: PILImage = self.image
        else:
            image = custom_image
        selection = self.get_selection_region()
        sprite = image.crop(selection)
        return sprite

    def find_unique_colors(self) -> List[List[int]]:
        self.progress.update(0.1)
        selection = self.get_selection_region()
        sprite = self.get_selection_image().convert("RGB")
        self.progress.update(5)

        image: PILImage = self.image.copy().convert("RGB")
        draw = ImageDraw.Draw(image)
        draw.rectangle(selection, fill=0)
        del draw

        self.progress.update(10)

        rest_pixels = np.unique(np.asarray(image.getdata()), axis=0).tolist()
        self.progress.update(30)
        sprite_pixels = np.unique(np.asarray(sprite.getdata()), axis=0).tolist()
        self.progress.update(50)
        unique_colors = [item for item in sprite_pixels if item not in rest_pixels]
        self.progress.update(90)

        if len(unique_colors) == 0:
            print("No unique colors found")
            self.progress.update(100)
            return []

        unique_colors.sort(reverse=True)
        self.progress.update(100)
        return unique_colors

    def save_image(self, name, image):
        p = Path(self.image_path)
        p = p.parents[0] / f"{name}_{self.date_for_filename()}.png"
        print(p)
        image.save(p)
        self.show_popup(f"File written to: [b]{p}[/b]")
        print("File written to:", p)

    def find_unique_press(self, *args):
        if not self.check_region_selected():
            return
        unique_colors = self.find_unique_colors()
        if len(unique_colors) == 0:
            self.show_popup("No unique colors found")
            return
        unique_colors = np.array([unique_colors])
        print(unique_colors)
        print(unique_colors.shape)
        unique_color_image = PILImage.fromarray(unique_colors.astype('uint8'), "RGB")

        self.save_image("unique", unique_color_image)

    def create_sprite_press(self, *args):
        if not self.check_region_selected():
            return
        sprite = self.get_selection_image()
        self.save_image("sprite", sprite)

    def toggle_grid_press(self, button, enabled, *args):
        self.viewer.toggle_grid(enabled)

    def on_image_path(self, *args):
        self.image = PILImage.open(self.image_path)  # CoreImage(path, keep_data=True)

    def load_image(self, path):
        self.image_path = path

    def pil_to_core(self, pil):
        image = pil.convert("RGB")
        image_file = io.BytesIO()

        image.save(image_file, "png")
        image_file.seek(0)

        return CoreImage(image_file, ext="png")

    def on_image(self, sender, image: PILImage):
        print("Image set")
        self.core_image = self.pil_to_core(image)
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


class RegionSelection(FloatLayout):
    sel_x = NumericProperty(0.0)
    sel_y = NumericProperty(0.0)
    sel_width = NumericProperty(0.0)
    sel_height = NumericProperty(0.0)
    visible = BooleanProperty(False)
    rect = ObjectProperty(None)

    @property
    def overlay(self):
        return self._overlay

    @overlay.setter
    def overlay(self, overlay):
        self._overlay = overlay
        if self._overlay is None:
            self.overlay_image.texture = None
            self.overlay_image.opacity = 0.0
        else:
            self.overlay_image.texture = self.overlay.texture
            self.overlay_image.opacity = 1.0

    def __init__(self, viewer: 'SpriteEditorViewer' = None, **kwargs):
        super(RegionSelection, self).__init__(**kwargs)
        self.viewer = viewer
        self.bind(sel_x=self.update, sel_y=self.update, sel_width=self.update, sel_height=self.update)
        self.bind(sel_x=self.update_overlay, sel_y=self.update_overlay, sel_width=self.update_overlay,
                  sel_height=self.update_overlay)
        self.viewer.image.bind(size=self.update, pos=self.update)
        self.viewer.bind(xscale=self.update, yscale=self.update)
        self.bind(visible=self.redraw)
        self.overlay_image = SpriteEditorImage(allow_stretch=True, nocache=True, size_hint=(None, None))
        self.add_widget(self.overlay_image)
        self.overlay_image.opacity = 0.0
        self._overlay: Optional[CoreImage] = None
        self.register_event_type('on_update')

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

    def on_update(self, *args):
        pass

    def update_overlay(self, *args):
        if self.sel_width > 0 and self.sel_height > 0:
            self.dispatch("on_update")
        else:
            self.overlay = None

    def update(self, *args):
        if self.rect is None:
            self.redraw()
            return

        self.rect.pos = self.viewer.image_pos_to_window((self.sel_x, self.sel_y + self.sel_height))
        self.rect.size = self.viewer.image_size_to_window(self.sel_width, self.sel_height)

        self.rect2.rectangle = (self.rect.pos[0], self.rect.pos[1], self.rect.size[0], self.rect.size[1])

        self.overlay_image.pos = self.rect.pos
        self.overlay_image.size = self.rect.size

        self.viewer.owner.sel_x_label.set_value(self.sel_x)
        self.viewer.owner.sel_y_label.set_value(self.sel_y)
        self.viewer.owner.sel_width_label.set_value(self.sel_width)
        self.viewer.owner.sel_height_label.set_value(self.sel_height)

    def redraw(self, *args):
        # self.canvas.clear()
        if not self.visible:
            self.opacity = 0.0
            return
        else:
            self.opacity = 1.0

        with self.canvas:
            Color(0.5, 1, 0.5, 0.3)
            self.rect = Rectangle()
            Color(1, 1, 0, 0.7)
            self.rect2 = Line(rectangle=(0, 0, 0, 0), width=1.2)
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

        self.grid = SpriteEditorGrid(owner=self.image, viewer=self, size_hint=(None, None))
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

        local_pos[0] = int(local_pos[0])
        local_pos[1] = int(local_pos[1])
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

    def __init__(self, owner: 'SpriteEditorImage' = None, viewer: SpriteEditorViewer = None, **kwargs):
        super(SpriteEditorGrid, self).__init__(**kwargs)
        self.owner = owner
        self.viewer = viewer
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

        if h_stride < 8 or v_stride < 8:
            return

        grid = InstructionGroup()

        startx = int(-self.owner.pos[0] / h_stride)
        if startx < 0:
            startx = 0

        starty = int(-self.owner.pos[1] / v_stride)
        if starty < 0:
            starty = 0

        endx = int(self.viewer.size[0] / h_stride + startx + 2)
        endy = int(self.viewer.size[1] / v_stride + starty + 2)
        if endy >= height + 1:
            endy = height + 1

        if endx >= width + 1:
            endx = width + 1

        grid.add(Color(1, 1, 1))
        for y in range(starty, endy):
            grid.add(Line(points=[int(self.x + 0), int(self.y + y * v_stride), int(self.x + self.width),
                                  int(self.y + y * v_stride)]))
        for x in range(startx, endx):
            grid.add(Line(points=[int(self.x + x * h_stride), int(self.y + 0), int(self.x + x * h_stride),
                                  int(self.y + self.height)]))

        self.canvas.add(grid)


class SpriteEditorImage(Image):
    def __init__(self, **kwargs):
        super(SpriteEditorImage, self).__init__(**kwargs)
        self.bind(texture=self.update_texture_filters)

    def update_texture_filters(self, *args):
        if self.texture == None: return
        self.texture.min_filter = 'nearest'
        self.texture.mag_filter = 'nearest'
