# One string, two layers, one pose. Gui.renderTitle draws the title at scale 4 and the subtitle at
# scale 2 (Gui.java:365-376), and skyview measures both: a red_lv cell in either slot reaches 100%
# of the frame, because the cell is 2.5x the viewport even half-scaled. The subtitle was still the
# wrong home for the burst's wash - it would cost a second title packet on every one of the fifty
# burst ticks, it leaves a slot that only `title @a reset` empties, and opening_done's hand-over
# would move the veil from a scale-2 box to the scale-4 one the rest of the song paints on. In this
# string the veil cell is the shipped title_red cell at the same pen and the same string width, which
# is what makes the cut invisible; the validator checks those two numbers instead of trusting this.
# The pen trick is the shipped one - an fx cell and a burst cell are both advance 1201, ink 1200,
# height 600, top -290 - so one deusex:tspace cell of -1201 walks the pen back exactly one cell and
# the blast lands on top of the wash instead of beside it. The outer pads are title_red's own pair,
# -602 in front and -602 behind, which hold the string width near -3 and put the veil cell's pen at
# x=-1924 GUI: the frame reads columns 40..60% of the cell, the same slice every other veil number
# in this pack was measured on. A burst frame's advance is its own ink width (1196 for frame 15),
# so the cell drifts by up to 12 GUI units across the sixteen frames and the sampled slice moves
# 0.25% - nothing, because red_lv.png lays one flat alpha over the whole cell.
# Order is the layering: shadow pass, then the veil, then the blast over it. Where a burst frame is
# transparent the red sky shows through, which is what makes the wash arrive with the explosion
# instead of replacing it.
$title @a title ["",{"text":"","font":"deusex:tspace"},{"text":"$(rc)","font":"deusex:fx"},{"text":"","font":"deusex:tspace"},{"text":"$(burst)","font":"deusex:burst"},{"text":"","font":"deusex:tspace"}]
