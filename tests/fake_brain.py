"""A rule-based stand-in for the model, used only to exercise the plumbing in tests.

It reads the same filtered screen text a model would, so it inherits each persona's limits.
"""
import json
import re


def make(name="Sam", phone="+63 917 123 4567"):
    state = {"tabs": 0, "phone_tries": 0, "screens": {}, "last": None}

    def complete(messages):
        sys_msg, user = messages[0]["content"], messages[-1]["content"]
        if "senior UX researcher" in user:
            return json.dumps({"findings": [{"title": "Size cups are unlabelled and unreachable by keyboard",
                                             "severity": "blocker", "who": ["Jo"], "evidence": "test", "fix": "Use buttons."}]})
        screen = user.split("What do you do next?")[0]
        state["screens"][screen[-400:]] = state["screens"].get(screen[-400:], 0) + 1
        if state["screens"][screen[-400:]] > 3:
            return json.dumps({"thought": "I keep pressing and nothing changes.", "action": "give_up nothing I do works"})
        if "You cannot click" in sys_msg:
            return keyboard(screen)
        return mouse(screen)

    def mouse(screen):
        lines = re.findall(r"\[(\d+)\] (control|text): (.+)", screen)
        txt = {r: t for r, k, t in lines}
        def find(pat, kind="control"):
            return next((r for r, k, t in lines if k == kind and re.search(pat, t, re.I)), None)
        if "Order placed" in screen:
            return json.dumps({"thought": "It says order placed.", "action": "done"})
        f = find(r"text field labelled '.*name.*' \(empty\)")
        if f:
            return json.dumps({"thought": "", "action": f"type {f} {name}"})
        ph = find(r"text field labelled '.*(phone|mobile).*'")
        if ph and "(empty)" in txt[ph]:
            state["phone_tries"] = 1
            return json.dumps({"thought": "", "action": f"type {ph} {phone}"})
        latte = find(r"^Iced Latte")
        if latte and "highlighted" not in txt[latte]:
            return json.dumps({"thought": "Iced latte.", "action": f"click {latte}"})
        icons = [r for r, k, t in lines if k == "control" and "unlabelled icon" in t]
        med = find(r"^Medium") or (icons[1] if len(icons) >= 3 else None)
        if med and "highlighted" not in txt[med]:
            guess = "icon" in txt[med]
            return json.dumps({"thought": "No labels on the cups, so I guess the middle one is medium." if guess else "",
                               "action": f"click {med}"})
        go = find(r"^(Continue|Place order)") or find(r"faint to read")
        if go:
            label = txt[go][:12]
            n = state["screens"].setdefault("go:" + label, 0)
            if ph and n >= 1 and state["phone_tries"] == 1 and ("red border" in txt[ph] or "starting with 09" in screen):
                state["phone_tries"] = 2
                why = "The message says to start with 09." if "starting with 09" in screen else "The phone box turned red but doesn't say why. Maybe it wants 09?"
                return json.dumps({"thought": why, "action": f"type {ph} 09171234567"})
            if n >= 3:
                return json.dumps({"thought": "", "action": "give_up I press it and nothing happens, and nothing tells me what's wrong"})
            state["screens"]["go:" + label] = n + 1
            th = "It looks greyed out, but there's nothing else to press." if "greyed" in txt[go] else (
                 "I can't read this pale bar; hoping it means next." if "faint" in txt[go] else "")
            return json.dumps({"thought": th, "action": f"click {go}"})
        return json.dumps({"thought": "I don't see what to do.", "action": "give_up I can't find a way forward"})

    def keyboard(screen):
        focus = re.search(r"KEYBOARD FOCUS IS ON: (.+)", screen)
        focus = focus.group(1) if focus else ""
        if "Order placed" in screen:
            return json.dumps({"thought": "Order placed was announced.", "action": "done"})
        if re.search(r"textbox '.*name", focus, re.I) and "value" not in focus:
            return json.dumps({"thought": "", "action": f"type_focused {name}"})
        if re.search(r"textbox '.*(phone|mobile)", focus, re.I):
            if "value" not in focus:
                return json.dumps({"thought": "", "action": f"type_focused {phone}"})
            if "starting with 09" in screen and "0917" not in focus.replace(" ", "")[:30] and state["phone_tries"] < 1:
                state["phone_tries"] += 1
                return json.dumps({"thought": "The error says to start with 09.", "action": "press Control+A"})
            if state["phone_tries"] == 1:
                state["phone_tries"] += 1
                return json.dumps({"thought": "", "action": "type_focused 09171234567"})
        targets = [r"Iced Latte", r"Medium", r"Continue", r"Place order"]
        if any(re.search(rf"button '{t}", focus) for t in targets) and "pressed true" not in focus:
            return json.dumps({"thought": "", "action": "press Enter"})
        if "starting with 09" in screen and state["phone_tries"] == 0:
            return json.dumps({"thought": "There's an error about the phone.", "action": "press Shift+Tab"})
        state["tabs"] += 1
        if state["tabs"] > 40:
            return json.dumps({"thought": "", "action": "give_up I can't reach the size or Continue controls"})
        return json.dumps({"thought": "", "action": "press Tab"})

    return complete
