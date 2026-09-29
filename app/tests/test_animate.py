"""Motion helpers: they must finish, and they must never strand the UI.

The failure that matters here is not "the animation looked wrong" -- it is
a card left permanently half-tinted, or a page left sitting 18 pixels low,
because the animation was cancelled or the widget went away mid-flight.
Every runner therefore writes the final value as its last act, and these
tests assert exactly that under each way it can be cut short.

Runs headless-ish: a real Tk root is created but never shown. Skipped
where there is no display at all.
"""
import tkinter as tk
import unittest

from app.utils import animate


def _root():
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - no display
        raise unittest.SkipTest("no Tk display: %s" % exc)
    root.withdraw()
    return root


class EasingTestCase(unittest.TestCase):

    def test_easing_starts_at_zero_and_ends_at_one(self):
        self.assertEqual(animate.ease_out_cubic(0.0), 0.0)
        self.assertEqual(animate.ease_out_cubic(1.0), 1.0)

    def test_easing_is_clamped_outside_the_unit_range(self):
        self.assertEqual(animate.ease_out_cubic(-5.0), 0.0)
        self.assertEqual(animate.ease_out_cubic(9.0), 1.0)

    def test_easing_only_ever_moves_forward(self):
        previous = -1.0
        for i in range(21):
            value = animate.ease_out_cubic(i / 20.0)
            self.assertGreaterEqual(value, previous)
            previous = value

    def test_it_eases_out_rather_than_in(self):
        """Most of the distance early: the UI should feel immediate."""
        self.assertGreater(animate.ease_out_cubic(0.5), 0.5)


class RunTestCase(unittest.TestCase):

    def setUp(self):
        self.root = _root()
        self.addCleanup(self.root.destroy)
        animate.set_enabled(True)
        self.addCleanup(animate.set_enabled, True)

    def _drain(self, ms=600):
        """Let Tk run its after() queue for a while."""
        done = {"flag": False}
        self.root.after(ms, lambda: done.__setitem__("flag", True))
        while not done["flag"]:
            self.root.update()

    def test_it_reaches_exactly_one_and_calls_done(self):
        seen, finished = [], []
        animate.run(self.root, 80, seen.append, done=lambda: finished.append(True))
        self._drain(400)
        self.assertEqual(seen[-1], 1.0, "did not finish on the final value")
        self.assertEqual(finished, [True])

    def test_it_makes_more_than_one_step(self):
        seen = []
        animate.run(self.root, 160, seen.append)
        self._drain(500)
        self.assertGreater(len(seen), 2, "that is a jump, not an animation")

    def test_values_never_go_backwards(self):
        seen = []
        animate.run(self.root, 120, seen.append)
        self._drain(450)
        self.assertEqual(seen, sorted(seen))

    def test_disabled_motion_still_applies_the_final_state(self):
        """The whole point of the switch: off means instant, not absent."""
        animate.set_enabled(False)
        seen = []
        animate.run(self.root, 500, seen.append)
        self.assertEqual(seen, [1.0], "should settle immediately, without a frame loop")

    def test_zero_duration_applies_the_final_state(self):
        seen = []
        animate.run(self.root, 0, seen.append)
        self.assertEqual(seen, [1.0])

    def test_a_destroyed_widget_ends_the_animation_quietly(self):
        child = tk.Frame(self.root)
        seen = []
        animate.run(child, 400, seen.append)
        child.destroy()
        self._drain(250)  # must not raise into the event loop

    def test_a_step_that_touches_a_dead_widget_does_not_raise(self):
        child = tk.Frame(self.root)

        def step(_t):
            child.configure(bg="#ff0000")

        animate.run(self.root, 300, step)
        child.destroy()
        self._drain(250)


class TintTestCase(unittest.TestCase):

    def setUp(self):
        self.root = _root()
        self.addCleanup(self.root.destroy)
        animate.set_enabled(True)
        self.addCleanup(animate.set_enabled, True)

    def _drain(self, ms=500):
        done = {"flag": False}
        self.root.after(ms, lambda: done.__setitem__("flag", True))
        while not done["flag"]:
            self.root.update()

    def test_a_tint_ends_on_the_destination_colour(self):
        frame = tk.Frame(self.root, bg="#000000")
        animate.tint_in(frame, "#000000", "#ffffff", duration_ms=80)
        self._drain(400)
        self.assertEqual(frame.cget("bg"), "#ffffff")

    def test_a_tint_passes_through_the_middle(self):
        seen = []
        frame = tk.Frame(self.root)
        animate.tint_in(frame, "#000000", "#ffffff", duration_ms=160,
                        apply=seen.append)
        self._drain(450)
        self.assertGreater(len(set(seen)), 2, "no intermediate shades")
        self.assertEqual(seen[-1], "#ffffff")

    def test_named_colours_work_not_just_hex(self):
        frame = tk.Frame(self.root)
        animate.tint_in(frame, "white", "black", duration_ms=60)
        self._drain(350)
        self.assertEqual(animate._rgb(frame.cget("bg"), frame), (0, 0, 0))

    def test_an_unparseable_colour_settles_on_the_destination(self):
        """Better a card that is the right colour instantly than one stuck
        on the page background because a theme key was renamed."""
        seen = []
        frame = tk.Frame(self.root)
        animate.tint_in(frame, "not-a-colour", "#123456", duration_ms=60,
                        apply=seen.append)
        self.assertEqual(seen[-1], "#123456")

    def test_disabled_motion_applies_the_destination_at_once(self):
        animate.set_enabled(False)
        seen = []
        frame = tk.Frame(self.root)
        animate.tint_in(frame, "#000000", "#ffffff", duration_ms=400,
                        apply=seen.append)
        self.assertEqual(seen, ["#ffffff"])


class SlideTestCase(unittest.TestCase):

    def setUp(self):
        self.root = _root()
        self.addCleanup(self.root.destroy)
        animate.set_enabled(True)
        self.addCleanup(animate.set_enabled, True)

    def _drain(self, ms=500):
        done = {"flag": False}
        self.root.after(ms, lambda: done.__setitem__("flag", True))
        while not done["flag"]:
            self.root.update()

    @staticmethod
    def _pady(widget):
        """(top, bottom) from pack_info.

        Tk hands back a plain int when pady was set as a scalar and a
        Python tuple when it was set as a pair -- not the Tcl "7 3" string
        the docs might lead you to expect.
        """
        value = widget.pack_info()["pady"]
        if isinstance(value, (tuple, list)):
            return (int(value[0]), int(value[-1]))
        return (int(value), int(value))

    def test_a_slide_ends_with_no_leftover_padding(self):
        """The one that would be visible forever if it went wrong."""
        frame = tk.Frame(self.root)
        frame.pack()
        animate.slide_in(frame, duration_ms=80, distance=20)
        self._drain(400)
        self.assertEqual(self._pady(frame), (0, 0))

    def test_a_slide_respects_the_padding_it_was_given(self):
        frame = tk.Frame(self.root)
        frame.pack(pady=(7, 3))
        animate.slide_in(frame, {"pady": (7, 3)}, duration_ms=80, distance=20)
        self._drain(400)
        self.assertEqual(self._pady(frame), (7, 3), "the resting layout moved")

    def test_a_slide_starts_offset(self):
        frame = tk.Frame(self.root)
        frame.pack()
        animate.slide_in(frame, duration_ms=300, distance=20)
        self.root.update()
        self.assertGreater(self._pady(frame)[0], 0, "it never left the ground")

    def test_disabled_motion_leaves_the_resting_layout(self):
        animate.set_enabled(False)
        frame = tk.Frame(self.root)
        frame.pack()
        animate.slide_in(frame, duration_ms=400, distance=20)
        self.assertEqual(self._pady(frame), (0, 0))


class EnabledFlagTestCase(unittest.TestCase):

    def tearDown(self):
        animate.set_enabled(True)

    def test_the_flag_round_trips(self):
        animate.set_enabled(False)
        self.assertFalse(animate.enabled())
        animate.set_enabled(True)
        self.assertTrue(animate.enabled())

    def test_it_coerces_truthiness(self):
        animate.set_enabled(0)
        self.assertIs(animate.enabled(), False)
        animate.set_enabled("yes")
        self.assertIs(animate.enabled(), True)

    def test_the_flag_is_shared_across_both_import_spellings(self):
        """This file is importable as `app.utils.animate` from the project
        root and as `utils.animate` from app/ -- which is how Start.bat runs
        the app. Python makes those two modules with two sets of globals, so
        a module-level flag meant switching motion off through one spelling
        left the other still animating.

        Loaded here under a third name to prove the flag is genuinely
        process-wide and not merely shared by luck of import order.
        """
        import importlib.util
        import os

        path = os.path.abspath(animate.__file__)
        spec = importlib.util.spec_from_file_location("_animate_other_name", path)
        other = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(other)

        self.assertIsNot(other, animate, "not actually a second module object")

        animate.set_enabled(False)
        self.assertFalse(other.enabled(), "the second copy kept animating")
        other.set_enabled(True)
        self.assertTrue(animate.enabled(), "the flag did not come back the other way")

    def test_a_second_copy_does_not_reset_the_flag_on_import(self):
        """Importing the module again mid-run must not silently switch
        motion back on underneath a caller that turned it off."""
        import importlib.util
        import os

        animate.set_enabled(False)
        spec = importlib.util.spec_from_file_location(
            "_animate_reimport", os.path.abspath(animate.__file__))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertFalse(animate.enabled(), "a re-import reset the flag")
        self.assertFalse(module.enabled())


if __name__ == "__main__":
    unittest.main()
