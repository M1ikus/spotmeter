// SpotMeterMenu.as
//
// Modal-ish settings dialog opened by the SpotMeter floating button. Phase
// 3.4 ships an empty frame with title + close button + dim background;
// Phase 4 fills the content area with tabs and widgets.
//
// Built for WoT 2.2.x (Scaleform GFx). Same Python-polling architecture
// as SpotMeterButton - no ExternalInterface, Python reads consume-on-read
// flags at 5 Hz.
//
// Python <-> AS3 contract (all methods callable via self.flashObject.NAME):
//
//   Python -> AS3 setters:
//     as_setStageSize(w:Number, h:Number)     // resize dim overlay
//     as_setTitle(text:String)
//
//   Python -> AS3 getters:
//     as_consumeClose():Boolean               // true once when user wants to close
//
// DAAPI lifecycle:
//     as_populate()                            // installs ESC listener
//     as_dispose()                             // removes ESC listener
//
// Close triggers (all set _pendingClose, Python polls):
//   - Click "Close" button at bottom-right of panel
//   - Click the X in panel title bar
//   - Click outside the panel (on the dim background)
//   - Press ESC key

package spotmeter {
    import flash.display.MovieClip;
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.KeyboardEvent;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;
    import flash.ui.Keyboard;

    public class SpotMeterMenu extends MovieClip {

        private static const PANEL_W:Number       = 600;
        private static const PANEL_H:Number       = 400;
        private static const TITLE_H:Number       = 36;

        private static const COLOR_DIM:uint       = 0x000000;
        private static const ALPHA_DIM:Number     = 0.55;
        private static const COLOR_PANEL:uint     = 0x222B36;
        private static const COLOR_PANEL_BORDER:uint = 0x7DB9E8;
        private static const COLOR_TITLE_BAR:uint = 0x2F3D4E;
        private static const COLOR_LABEL:uint     = 0xFFFFFF;
        private static const COLOR_CLOSE_BTN:uint = 0x3C4D60;
        private static const COLOR_CLOSE_HOVER:uint = 0x6B829A;

        private var _dim:Shape;
        private var _panel:Sprite;
        private var _titleBar:Shape;
        private var _title:TextField;
        private var _xBtn:Sprite;
        private var _closeBtn:Sprite;
        private var _contentBg:Shape;   // placeholder for Phase 4 widgets

        private var _stageW:Number = 1920;
        private var _stageH:Number = 1080;

        private var _pendingClose:Boolean = false;

        public function SpotMeterMenu() {
            super();

            // Dim background: clickable, sized to stage, dispatches close.
            _dim = new Shape();
            addChild(_dim);
            _dim.addEventListener(MouseEvent.CLICK, _onDimClick);

            // Panel
            _panel = new Sprite();
            _panel.mouseEnabled = true;
            // mouseChildren stays true so the X / Close buttons get clicks
            addChild(_panel);

            // Title bar background + title text
            _titleBar = new Shape();
            _panel.addChild(_titleBar);

            _title = new TextField();
            _title.selectable = false;
            _title.mouseEnabled = false;
            _title.autoSize = TextFieldAutoSize.LEFT;
            var titleFmt:TextFormat = new TextFormat();
            titleFmt.font = "Arial";
            titleFmt.size = 14;
            titleFmt.bold = true;
            titleFmt.color = COLOR_LABEL;
            _title.defaultTextFormat = titleFmt;
            _title.text = "SpotMeter Settings";
            _panel.addChild(_title);

            // X (close) button in top-right of title bar
            _xBtn = _makeIconButton("X", 24, 22);
            _xBtn.addEventListener(MouseEvent.CLICK, _onCloseClick);
            _panel.addChild(_xBtn);

            // Content background (Phase 4 will fill it with tabs/widgets)
            _contentBg = new Shape();
            _panel.addChild(_contentBg);

            // "Close" button at bottom-right
            _closeBtn = _makeTextButton("Close", 80, 26);
            _closeBtn.addEventListener(MouseEvent.CLICK, _onCloseClick);
            _panel.addChild(_closeBtn);

            // Block clicks from passing through the panel to the dim layer
            _panel.addEventListener(MouseEvent.CLICK, _swallowPanelClick);

            _redraw();
            _layout();
        }

        // ---------- DAAPI lifecycle ----------

        public function as_populate():void {
            if (stage != null) {
                stage.addEventListener(KeyboardEvent.KEY_DOWN, _onStageKeyDown);
                _stageW = stage.stageWidth;
                _stageH = stage.stageHeight;
                _redraw();
                _layout();
            }
        }

        public function as_dispose():void {
            if (stage != null) {
                stage.removeEventListener(KeyboardEvent.KEY_DOWN, _onStageKeyDown);
            }
            _dim.removeEventListener(MouseEvent.CLICK, _onDimClick);
            _xBtn.removeEventListener(MouseEvent.CLICK, _onCloseClick);
            _closeBtn.removeEventListener(MouseEvent.CLICK, _onCloseClick);
            _panel.removeEventListener(MouseEvent.CLICK, _swallowPanelClick);
        }

        // ---------- Python -> AS3 ----------

        public function as_setStageSize(w:Number, h:Number):void {
            _stageW = w;
            _stageH = h;
            _redraw();
            _layout();
        }

        public function as_setTitle(text:String):void {
            _title.text = text;
            _layout();
        }

        public function as_consumeClose():Boolean {
            var was:Boolean = _pendingClose;
            _pendingClose = false;
            return was;
        }

        // ---------- Drawing ----------

        private function _redraw():void {
            // Dim overlay covers whole stage
            var d:* = _dim.graphics;
            d.clear();
            d.beginFill(COLOR_DIM, ALPHA_DIM);
            d.drawRect(0, 0, _stageW, _stageH);
            d.endFill();

            // Panel body (drawn into _panel at local origin; positioned in _layout)
            // Drop the previous shape data and redraw onto the title bar +
            // content bg shapes inside the panel.
            var tb:* = _titleBar.graphics;
            tb.clear();
            tb.beginFill(COLOR_TITLE_BAR, 1.0);
            tb.drawRoundRectComplex(0, 0, PANEL_W, TITLE_H, 8, 8, 0, 0);
            tb.endFill();

            var cb:* = _contentBg.graphics;
            cb.clear();
            cb.beginFill(COLOR_PANEL, 1.0);
            cb.drawRoundRectComplex(0, TITLE_H, PANEL_W, PANEL_H - TITLE_H, 0, 0, 8, 8);
            cb.endFill();

            // Panel outline
            // Drawn on the panel's own graphics layer (below title bar/content
            // children since we use a Sprite, but it sits behind because we
            // draw outline after the children in display order via shapes).
            // Simpler: outline on top via a dedicated graphics call on _panel.
            var pg:* = _panel.graphics;
            pg.clear();
            pg.lineStyle(1, COLOR_PANEL_BORDER, 0.9);
            pg.drawRoundRect(0, 0, PANEL_W, PANEL_H, 8, 8);
        }

        private function _layout():void {
            // Center the panel on stage
            _panel.x = Math.round((_stageW - PANEL_W) / 2);
            _panel.y = Math.round((_stageH - PANEL_H) / 2);

            // Title text centered vertically in title bar, left-padded
            _title.x = 14;
            _title.y = (TITLE_H - _title.height) / 2;

            // X button top-right of title bar
            _xBtn.x = PANEL_W - _xBtn.width - 6;
            _xBtn.y = (TITLE_H - _xBtn.height) / 2;

            // Close button bottom-right of panel
            _closeBtn.x = PANEL_W - _closeBtn.width - 16;
            _closeBtn.y = PANEL_H - _closeBtn.height - 14;
        }

        // ---------- Internal helpers ----------

        private function _makeTextButton(label:String, w:Number, h:Number):Sprite {
            var s:Sprite = new Sprite();
            s.buttonMode = true;
            s.useHandCursor = true;

            var bg:Shape = new Shape();
            s.addChild(bg);

            var fmt:TextFormat = new TextFormat();
            fmt.font = "Arial";
            fmt.size = 12;
            fmt.bold = true;
            fmt.color = COLOR_LABEL;

            var tf:TextField = new TextField();
            tf.selectable = false;
            tf.mouseEnabled = false;
            tf.autoSize = TextFieldAutoSize.LEFT;
            tf.defaultTextFormat = fmt;
            tf.text = label;
            s.addChild(tf);

            // Initial paint
            _paintButton(bg, w, h, false);
            tf.x = (w - tf.width)  / 2;
            tf.y = (h - tf.height) / 2;

            s.addEventListener(MouseEvent.ROLL_OVER, function(e:MouseEvent):void {
                _paintButton(bg, w, h, true);
            });
            s.addEventListener(MouseEvent.ROLL_OUT, function(e:MouseEvent):void {
                _paintButton(bg, w, h, false);
            });
            return s;
        }

        private function _makeIconButton(glyph:String, w:Number, h:Number):Sprite {
            // Same as text button, smaller, single-char label.
            return _makeTextButton(glyph, w, h);
        }

        private function _paintButton(bg:Shape, w:Number, h:Number, hover:Boolean):void {
            var g:* = bg.graphics;
            g.clear();
            g.beginFill(hover ? COLOR_CLOSE_HOVER : COLOR_CLOSE_BTN, 1.0);
            g.lineStyle(1, COLOR_PANEL_BORDER, 0.7);
            g.drawRoundRect(0, 0, w, h, 4, 4);
            g.endFill();
        }

        // ---------- Event handlers ----------

        private function _onDimClick(e:MouseEvent):void {
            _pendingClose = true;
        }

        private function _onCloseClick(e:MouseEvent):void {
            e.stopImmediatePropagation();
            _pendingClose = true;
        }

        private function _swallowPanelClick(e:MouseEvent):void {
            // Prevents panel clicks from bubbling to the dim layer.
            e.stopPropagation();
        }

        private function _onStageKeyDown(e:KeyboardEvent):void {
            if (e.keyCode == Keyboard.ESCAPE) {
                _pendingClose = true;
            }
        }
    }
}
