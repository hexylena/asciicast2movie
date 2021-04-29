'''
rendering pyte terminal emulator screen as image

Should be imported as a module and contains functions:
  * tty2img - convert pyte screen to PIL image

Requires:
  * PIL (https://pypi.org/project/Pillow/) image library
  * pyte (https://pypi.org/project/pyte/) VTXXX terminal emulator
  * fclist (https://pypi.org/project/fclist-cffi/) fontconfig wrapper
    (optional, for support fallback fonts)
  * freetype (https://pypi.org/project/freetype-py/) freetype wrapper
    (optional, for support fallback fonts)

Copyright © 2020-2021, Robert Ryszard Paciorek <rrp@opcode.eu.org>,
                       MIT licence
'''

from PIL import Image, ImageDraw, ImageFont, ImageColor
import copy
import functools
import pyte

# import fclist
import freetype

class tty2img:

    def __init__(
        self,
        screen,
        fgDefaultColor = 'black',
        bgDefaultColor = 'white',
        fontName            = 'DejaVuSansMono.ttf',
        boldFontName        = 'DejaVuSansMono-Bold.ttf',
        italicsFontName     = 'DejaVuSansMono-Oblique.ttf',
        boldItalicsFontName = 'DejaVuSansMono-BoldOblique.ttf',
        fallbackFonts       = ['DroidSansFallback', 'Symbola'],
        fontSize     = 16,
        lineSpace    = 0,
        marginSize   = 10,
        antialiasing = 0,
        showCursor   = False,
        logFunction  = None
    ):
        '''Render pyte screen as PIL image

        Parameters
        ----------
        screen : pyte.Screen
            with terminal state to render
        fgDefaultColor : str, optional
            default foreground (e.g. text) color for rendered screen
        bgDefaultColor : str, optional
            default background color for rendered screen
        fontName : str, optional
        boldFontName : str, optional
        italicsFontName : str, optional
        boldItalicsFontName : str, optional
            font filepath or filename (in default font location) for:
                * standard font (fontName)
                * bold font (boldFontName)
                * italics font (italicsFontName)
                * bold+italics font (boldItalicsFontName)
            should be used monospace font from this same family
            (for all chars and all font variants char width should be the same)
        fallbackFonts : list of strings
            fonts families to use when normal font don't have glyph for
            rendered character (require fclist module)
        fontSize : int, optional
            font size to use
        lineSpace : int, optional
            extra space between lines in pixels
        marginSize : int, optional
            margin size (left = right = top = bottom) for rendered screen
        antialiasing : int, optional
            antialiasing level, when greater than 1 rendered image
            will be antialiasing times greater ans scale down
        showCursor : bool, optional
            when true (and screen.cursor.hidden is false) mark cursor position
            by reverse foreground background color on it
        logFunction : function
            function used to print some info and warnings,
            e.g. set to print for printing to stdout

        Returns
        -------
            PIL.Image
                with rendered terminal screen
        '''
        self.antialiasing = antialiasing
        if antialiasing > 1:
            self.lineSpace    = lineSpace * antialiasing
            self.marginSize   = marginSize * antialiasing
            self.fontSize     = fontSize * antialiasing
        else:
            self.lineSpace    = lineSpace
            self.marginSize   = marginSize
            self.fontSize     = fontSize

        # Recalc fontsize to ensure it fits nicely.
        for i in range(8, 64):
            f = ImageFont.truetype(fontName, i)
            cw, _ = f.getsize('X')
            ch    = sum(f.getmetrics()) + lineSpace
            iw = cw * screen.columns + 2*marginSize
            ih = ch * screen.lines + 2*marginSize
            print(i, ih, iw)
            if iw > 1920 or ih > 1080:
                fontSize = i
                break

        # font settings
        self.normalFont      = [ ImageFont.truetype(fontName, fontSize), None ]
        self.boldFont        = [ ImageFont.truetype(boldFontName, fontSize), None ]
        self.italicsFont     = [ ImageFont.truetype(italicsFontName, fontSize), None ]
        self.boldItalicsFont = [ ImageFont.truetype(boldItalicsFontName, fontSize), None ]

        self.normalFont[1]      = freetype.Face(self.normalFont[0].path)
        self.boldFont[1]        = freetype.Face(self.boldFont[0].path)
        self.italicsFont[1]     = freetype.Face(self.italicsFont[0].path)
        self.boldItalicsFont[1] = freetype.Face(self.boldItalicsFont[0].path)

        # calculate single char and image size
        self.charWidth, _ = self.normalFont[0].getsize('X')
        self.charHeight   = sum(self.normalFont[0].getmetrics()) + lineSpace
        self.imgWidth     = 1920 # charWidth  * screen.columns + 2*marginSize
        self.imgHeight    = 1080 # charHeight * screen.lines + 2*marginSize


        # cols/lines should have been

        # create image object
        self.bgDefaultColor = bgDefaultColor
        self.fgDefaultColor = fgDefaultColor
        self.base_image = Image.new('RGBA', (self.imgWidth, self.imgHeight), self.bgDefaultColor)
        self.base_draw = ImageDraw.Draw(self.base_image)
        self.showCursor = showCursor


    @functools.lru_cache()
    def memofont(self, font0, font1, char):
        font = [font0, font1]
        extraWidth = 0
        if not font[1].get_char_index(char):
            foundFont = False
            for fname in fallbackFonts:
                for ff in fclist.fclist(family=fname, charset=hex(ord(cData.data))):
                    foundFont = True
                    font = [ ImageFont.truetype(ff.file, fontSize), None ]
                    extraWidth = max(0, font[0].getsize(cData.data)[0] - self.charWidth)
                    break
                if foundFont:
                    break
            else:
                if logFunction:
                    logFunction("Missing glyph for " + hex(ord(cData.data)) + " Unicode symbols (" + cData.data + ")")
        return (extraWidth, font)

    def render(self, screen):
        image = self.base_image.copy()
        draw = ImageDraw.Draw(image)

        # cursor settings
        self.showCursor = self.showCursor and (not screen.cursor.hidden)

        # draw full screen to image
        for line in screen.buffer:
            # process all characters in line
            point, char, lchar = [self.marginSize, line*self.charHeight + self.marginSize], -1, -1
            for char in sorted(screen.buffer[line].keys()):
                cData = screen.buffer[line][char]

                # check for skipped chars (e.g. when use \t)
                point[0] += self.charWidth * (char - lchar - 1)
                lchar = char

                # check for empty char (bug in pyte?)
                if cData.data == "":
                    continue

                # set colors and draw background
                bgColor = cData.bg if cData.bg != 'default' else self.bgDefaultColor
                fgColor = cData.fg if cData.fg != 'default' else self.fgDefaultColor

                if cData.reverse:
                    bgColor, fgColor = fgColor, bgColor

                if self.showCursor and line == screen.cursor.y and char == screen.cursor.x:
                    bgColor, fgColor = fgColor, bgColor

                bgColor = _convertColor(bgColor)
                fgColor = _convertColor(fgColor)

                if bgColor != self.bgDefaultColor:
                    draw.rectangle( ((point[0], point[1]), (point[0] + self.charWidth, point[1] + self.charHeight)), fill=bgColor )

                # set font (bold / italics)
                if cData.bold and cData.italics:
                    font = self.boldItalicsFont
                elif cData.bold:
                    font = self.boldFont
                elif cData.italics:
                    font = self.italicsFont
                else:
                    font = self.normalFont

                # does font have this char?
                (extraWidth, font) = self.memofont(font[0], font[1], cData.data)

                # draw underscore and strikethrough
                if cData.underscore:
                    draw.line(((point[0], point[1] + self.charHeight-1), (point[0] + self.charWidth, point[1] + self.charHeight-1)), fill=fgColor)

                if cData.strikethrough:
                    draw.line(((point[0], point[1] + self.charHeight//2), (point[0] + self.charWidth, point[1] + self.charHeight//2)), fill=fgColor)

                # draw text
                draw.text(point, cData.data, fill=fgColor, font=font[0])

                # update next char position
                point[0] += self.charWidth + extraWidth

            # draw cursor when it is out of text range
            if self.showCursor and line == screen.cursor.y and (not screen.cursor.x in screen.buffer[line]):
                point[0] += (screen.cursor.x - char - 1) * self.charWidth
                draw.rectangle( ((point[0], point[1]), (point[0] + self.charWidth, point[1] + self.charHeight)), fill=self.fgDefaultColor )

        # return image
        if self.antialiasing > 1:
            return image.resize((self.imgWidth//self.antialiasing, self.imgHeight//self.antialiasing), Image.ANTIALIAS)
        else:
            return image

def _convertColor(color):
    if color[0] != "#" and not color in ImageColor.colormap:
        return "#" + color
    return color
