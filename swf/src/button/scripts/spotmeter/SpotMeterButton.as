// SpotMeterButton.as
//
// Floating SpotMeter menu trigger for the WoT hangar. Drag with mouse to
// reposition; persists across WoT restarts via Python config save.
//
// Built for WoT 2.2.x (Scaleform GFx). ExternalInterface is NOT used (it
// doesn't bridge to Python in Scaleform). Instead, the Python view polls
// our state at ~5 Hz via the DAAPI bridge (self.flashObject.as_*()), and
// we expose two consume-on-read flags for click and drag-end.
//
// Python <-> AS3 contract (all methods callable via self.flashObject.NAME):
//
//   Python -> AS3 setters:
//     as_setSize(w:Number, h:Number)
//     as_setLabel(text:String)
//     as_setPosition(x:Number, y:Number)
//
//   Python -> AS3 getters:
//     as_getX():Number
//     as_getY():Number
//     as_consumeClick():Boolean         (returns true once per click, then clears)
//     as_consumeDragEnd():Boolean       (returns true once per drag-release)
//
// DAAPI lifecycle stubs (called by WG framework automatically):
//     as_populate()                     (no-op; we set state lazily)
//     as_dispose()                      (cleans up stage listeners)
//
// Drag vs click discrimination: mouse-down captures the start position;
// if pointer moves more than DRAG_THRESHOLD px before mouse-up it's a
// drag (sets _pendingDragEnd), else a click (sets _pendingClick).

package spotmeter {
    import flash.display.MovieClip;
    import flash.display.Shape;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;

    public class SpotMeterButton extends MovieClip {

        private static const DRAG_THRESHOLD:Number = 5.0;
        private static const COLOR_BG:uint        = 0x2C3E50;
        private static const COLOR_BG_HOVER:uint  = 0x4A6378;
        private static const COLOR_BORDER:uint    = 0x7DB9E8;
        private static const COLOR_LABEL:uint     = 0xFFFFFF;
        private static const ALPHA_BG:Number      = 0.85;
        private static const ALPHA_BORDER:Number  = 0.90;
        private static const CORNER_RADIUS:Number = 6;

        private var _bg:Shape;
        private var _label:TextField;
        private var _w:Number = 90;
        private var _h:Number = 28;

        // Drag state
        private var _dragging:Boolean = false;
        private var _dragStartMouseX:Number = 0;
        private var _dragStartMouseY:Number = 0;
        private var _dragOffsetX:Number = 0;
        private var _dragOffsetY:Number = 0;

        // Consume-on-read flags (Python polls)
        private var _pendingClick:Boolean = false;
        private var _pendingDragEnd:Boolean = false;

        public function SpotMeterButton() {
            super();
            _bg = new Shape();
            addChild(_bg);

            _label = new TextField();
            _label.selectable = false;
            _label.mouseEnabled = false;
            _label.autoSize = TextFieldAutoSize.LEFT;
            var fmt:TextFormat = new TextFormat();
            fmt.font = "Arial";
            fmt.size = 12;
            fmt.bold = true;
            fmt.color = COLOR_LABEL;
            _label.defaultTextFormat = fmt;
            _label.text = "SpotMeter";
            addChild(_label);

            _redraw(false);
            _layout();

            this.buttonMode = true;
            this.useHandCursor = true;
            this.mouseChildren = false;

            addEventListener(MouseEvent.MOUSE_DOWN, _onMouseDown);
            addEventListener(MouseEvent.ROLL_OVER,  _onRollOver);
            addEventListener(MouseEvent.ROLL_OUT,   _onRollOut);
        }

        // ---------- DAAPI lifecycle stubs ----------

        public function as_populate():void {
            // No-op. Python will configure us via as_setSize / as_setPosition
            // immediately after populate.
        }

        public function as_dispose():void {
            if (stage != null) {
                stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onStageMouseMove);
                stage.removeEventListener(MouseEvent.MOUSE_UP,   _onStageMouseUp);
            }
            removeEventListener(MouseEvent.MOUSE_DOWN, _onMouseDown);
            removeEventListener(MouseEvent.ROLL_OVER,  _onRollOver);
            removeEventListener(MouseEvent.ROLL_OUT,   _onRollOut);
        }

        // ---------- Python -> AS3 setters ----------

        public function as_setSize(w:Number, h:Number):void {
            _w = w;
            _h = h;
            _redraw(false);
            _layout();
        }

        public function as_setLabel(text:String):void {
            _label.text = text;
            _layout();
        }

        public function as_setPosition(px:Number, py:Number):void {
            // Clamp to stage bounds so coords saved at a different resolution
            // can't push the button off-screen on this run.
            if (stage != null) {
                var maxX:Number = Math.max(0, stage.stageWidth  - _w);
                var maxY:Number = Math.max(0, stage.stageHeight - _h);
                px = Math.max(0, Math.min(px, maxX));
                py = Math.max(0, Math.min(py, maxY));
            }
            this.x = px;
            this.y = py;
        }

        // ---------- Python -> AS3 getters / consume-on-read ----------

        public function as_getX():Number {
            return this.x;
        }

        public function as_getY():Number {
            return this.y;
        }

        public function as_consumeClick():Boolean {
            var was:Boolean = _pendingClick;
            _pendingClick = false;
            return was;
        }

        public function as_consumeDragEnd():Boolean {
            var was:Boolean = _pendingDragEnd;
            _pendingDragEnd = false;
            return was;
        }

        // ---------- Internal drawing / layout ----------

        private function _redraw(hover:Boolean):void {
            var g:* = _bg.graphics;
            g.clear();
            g.beginFill(hover ? COLOR_BG_HOVER : COLOR_BG, ALPHA_BG);
            g.lineStyle(1, COLOR_BORDER, ALPHA_BORDER);
            g.drawRoundRect(0, 0, _w, _h, CORNER_RADIUS, CORNER_RADIUS);
            g.endFill();
        }

        private function _layout():void {
            _label.x = (_w - _label.width)  / 2;
            _label.y = (_h - _label.height) / 2;
        }

        // ---------- Hover ----------

        private function _onRollOver(e:MouseEvent):void {
            _redraw(true);
        }

        private function _onRollOut(e:MouseEvent):void {
            if (!_dragging) {
                _redraw(false);
            }
        }

        // ---------- Drag-and-drop ----------

        private function _onMouseDown(e:MouseEvent):void {
            if (stage == null) return;
            _dragStartMouseX = stage.mouseX;
            _dragStartMouseY = stage.mouseY;
            _dragOffsetX = stage.mouseX - this.x;
            _dragOffsetY = stage.mouseY - this.y;
            _dragging = false;
            stage.addEventListener(MouseEvent.MOUSE_MOVE, _onStageMouseMove);
            stage.addEventListener(MouseEvent.MOUSE_UP,   _onStageMouseUp);
        }

        private function _onStageMouseMove(e:MouseEvent):void {
            if (stage == null) return;
            var dx:Number = stage.mouseX - _dragStartMouseX;
            var dy:Number = stage.mouseY - _dragStartMouseY;
            if (!_dragging && (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD)) {
                _dragging = true;
            }
            if (_dragging) {
                var nx:Number = stage.mouseX - _dragOffsetX;
                var ny:Number = stage.mouseY - _dragOffsetY;
                var maxX:Number = Math.max(0, stage.stageWidth  - _w);
                var maxY:Number = Math.max(0, stage.stageHeight - _h);
                this.x = Math.max(0, Math.min(nx, maxX));
                this.y = Math.max(0, Math.min(ny, maxY));
            }
        }

        private function _onStageMouseUp(e:MouseEvent):void {
            if (stage != null) {
                stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onStageMouseMove);
                stage.removeEventListener(MouseEvent.MOUSE_UP,   _onStageMouseUp);
            }
            if (_dragging) {
                _dragging = false;
                _redraw(false);
                _pendingDragEnd = true;
            } else {
                _pendingClick = true;
            }
        }
    }
}
