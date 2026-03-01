from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.geometry import Offset

class FadingScrollContainer(VerticalScroll):
    """A container where scrollbars fade out after inactivity."""
    def on_mount(self) -> None:
        self.add_class("hide-scrollbars")
        self.fade_timer = None

    def watch_scroll_offset(self, old_value: Offset, new_value: Offset) -> None:
        self.remove_class("hide-scrollbars")
        if self.fade_timer:
            self.fade_timer.cancel()
        self.fade_timer = self.set_timer(2.0, self.hide_scrollbars)

    def hide_scrollbars(self) -> None:
        self.add_class("hide-scrollbars")
