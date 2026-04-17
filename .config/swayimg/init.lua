swayimg.enable_overlay(false)
swayimg.set_mode("viewer")
swayimg.enable_decoration(false)
swayimg.enable_overlay(true)
swayimg.set_window_size(1280, 720)

swayimg.viewer.set_default_scale("fit")
swayimg.viewer.set_window_background(0x00000000)
swayimg.viewer.enable_loop(true)

-- Hide text overlay
swayimg.text.set_timeout(0)
swayimg.viewer.set_text("topleft", {})
swayimg.viewer.set_text("topright", {})
swayimg.viewer.set_text("bottomleft", {})

-- Navigation
swayimg.viewer.on_key("Right", function()
swayimg.viewer.switch_image("next")
end)
swayimg.viewer.on_key("Left", function()
swayimg.viewer.switch_image("prev")
end)

-- Enter = apply wallpaper
swayimg.viewer.on_key("Return", function()
local image = swayimg.viewer.get_image()
local f = io.open("/home/creed/.cache/wallpaper-preview-selected", "w")
f:write(image.path)
f:close()
swayimg.exit()
end)

swayimg.viewer.on_key("Escape", function()
swayimg.exit()
end)

swayimg.on_initialized(function()
swayimg.set_window_size(1280, 720)
os.execute("hyprctl dispatch moveactive exact 640 404")
end)
