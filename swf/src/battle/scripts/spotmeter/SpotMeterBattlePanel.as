// SpotMeterBattlePanel.as
//
// Always-visible floating panel for in-battle picker control. Replaces the
// chat-based live-mode status block with a graphical UI that lets the user
// pick an enemy by clicking, toggle picker perks/equipment, and flip
// auto-pick by distance.
//
// Built for WoT 2.2.x (Scaleform GFx). Same Python-polling architecture as
// SpotMeterButton / SpotMeterMenu - no ExternalInterface; Python polls at
// 5 Hz via DAAPI flashObject.as_*() bridge.
//
// Layout (top to bottom):
//   [title bar, draggable]
//   Target: <name>  VR=<m>
//   [ ] auto (dist)
//   Ulepszacze (toggles):
//     [x] rations  [x] BIA  [x] recon+sit
//     [ ] dyrektywy  [ ] field upgr.
//   Lista (click row to pick):
//     ● Obj. 907    335m  T10 MT
//     ○ Rhm.-B. WT  395m  T10 TD
//     ...
//
// Python <-> AS3 contract (all callable via self.flashObject.NAME):
//
//   Python -> AS3 setters:
//     as_setSize(w:Number, h:Number)
//     as_setPosition(x:Number, y:Number)
//     as_setEnemies(vids:Array, labels:Array, classCodes:Array)
//                                  // parallel arrays; label = "Obj. 907 T10",
//                                  // classCode in {"HT","MT","LT","TD","SPG"}
//     as_setSelected(vid:Number, name:String, vr:Number)
//                                  // vid=0 means no selection
//     as_setToggles(r:Boolean, b:Boolean, rs:Boolean, d:Boolean, fu:Boolean)
//                                  // rations, BIA, reconSitAware, directives, fieldUpgrades
//     as_setAutoPick(enabled:Boolean)
//
//   Python -> AS3 getters:
//     as_getX():Number
//     as_getY():Number
//
//   Python -> AS3 consume-on-read (returns event, then clears):
//     as_consumeSelectedVid():Number     0 if no click since last call
//     as_consumeToggleName():String      "" if no click; otherwise toggle key
//     as_consumeAutoPickClick():Boolean
//     as_consumeDragEnd():Boolean
//
// DAAPI lifecycle stubs (WG framework calls these automatically):
//   as_populate()
//   as_dispose()

package spotmeter {
    import flash.display.MovieClip;
    import flash.display.Shape;
    import flash.display.Sprite;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;

    public class SpotMeterBattlePanel extends MovieClip {

        // --- Layout constants ---
        private static const HEADER_H:Number       = 22;
        private static const ROW_H:Number          = 16;
        private static const SECTION_GAP:Number    = 6;
        private static const PAD_X:Number          = 8;
        private static const PAD_Y:Number          = 6;
        private static const CHECKBOX_SIZE:Number  = 11;
        private static const DRAG_THRESHOLD:Number = 5.0;
        private static const MAX_ENEMY_ROWS:Number = 15;

        // --- Colors (match SpotMeterMenu palette) ---
        private static const COLOR_BG:uint            = 0x222B36;
        private static const COLOR_BG_HEADER:uint     = 0x2F3D4E;
        private static const COLOR_BORDER:uint        = 0x7DB9E8;
        private static const COLOR_LABEL:uint        = 0xFFFFFF;
        private static const COLOR_LABEL_DIM:uint     = 0xC8D6E6;
        private static const COLOR_ROW_PICKED:uint    = 0x4A6378;
        private static const COLOR_ROW_HOVER:uint     = 0x3A4D60;
        private static const COLOR_CHECK_ON:uint      = 0x7DB9E8;
        private static const COLOR_CHECK_OFF:uint     = 0x4A5868;
        private static const COLOR_SECTION_HEAD:uint  = 0x88AABB;

        private static const ALPHA_BG:Number          = 0.85;

        // --- State held in this view ---
        private var _w:Number = 280;
        private var _h:Number = 360;

        // enemies parallel arrays
        private var _vids:Array        = [];
        private var _labels:Array      = [];
        private var _classCodes:Array  = [];

        // selected (current pick) info pushed from Python
        private var _selVid:Number    = 0;
        private var _selName:String   = '';
        private var _selVr:Number     = 0;

        // toggles
        private var _tRations:Boolean       = true;
        private var _tBIA:Boolean           = true;
        private var _tReconSit:Boolean      = true;
        private var _tDirectives:Boolean    = false;
        private var _tFieldUpgr:Boolean     = false;
        private var _autoPick:Boolean       = false;

        // --- Display objects ---
        private var _bg:Shape;
        private var _header:Sprite;
        private var _headerLabel:TextField;
        private var _content:Sprite;  // holds everything below header
        private var _targetText:TextField;
        private var _autoBox:Sprite;
        private var _autoLabel:TextField;
        private var _toggleHeader:TextField;
        private var _toggleRow1:Sprite;
        private var _toggleRow2:Sprite;
        private var _listHeader:TextField;
        private var _rowsContainer:Sprite;

        // --- Drag state ---
        private var _dragging:Boolean = false;
        private var _dragStartMX:Number = 0;
        private var _dragStartMY:Number = 0;
        private var _dragOffX:Number = 0;
        private var _dragOffY:Number = 0;

        // --- Consume-on-read flags / values ---
        private var _pendingVid:Number       = 0;    // 0 = no click
        private var _pendingToggle:String    = '';
        private var _pendingAutoClick:Boolean = false;
        private var _pendingDragEnd:Boolean   = false;

        public function SpotMeterBattlePanel() {
            super();

            _bg = new Shape();
            addChild(_bg);

            // Header (title bar + drag handle)
            _header = new Sprite();
            _header.buttonMode = true;
            _header.useHandCursor = true;
            _header.mouseChildren = false;
            addChild(_header);

            _headerLabel = _makeLabel('SpotMeter', 12, true, COLOR_LABEL);
            _header.addChild(_headerLabel);

            // Content container below header
            _content = new Sprite();
            addChild(_content);

            _targetText = _makeLabel('Target: --  VR=--m', 11, false, COLOR_LABEL);
            _content.addChild(_targetText);

            // Auto-pick checkbox row
            _autoBox = _makeCheckbox(false);
            _autoBox.addEventListener(MouseEvent.CLICK, _onAutoPickClick);
            _content.addChild(_autoBox);

            _autoLabel = _makeLabel('auto (dist)', 11, false, COLOR_LABEL);
            _autoLabel.mouseEnabled = false;
            _content.addChild(_autoLabel);

            // Toggles section
            _toggleHeader = _makeLabel('Ulepszacze:', 11, true, COLOR_SECTION_HEAD);
            _content.addChild(_toggleHeader);

            _toggleRow1 = new Sprite();
            _toggleRow2 = new Sprite();
            _content.addChild(_toggleRow1);
            _content.addChild(_toggleRow2);
            _buildToggleRows();

            // Enemy list section
            _listHeader = _makeLabel('Lista (klik = wybor):', 11, true, COLOR_SECTION_HEAD);
            _content.addChild(_listHeader);

            _rowsContainer = new Sprite();
            _content.addChild(_rowsContainer);

            // Drag bound to header only (so list-row clicks aren't captured)
            _header.addEventListener(MouseEvent.MOUSE_DOWN, _onHeaderDown);

            _redraw();
            _layout();
        }

        // ---------- DAAPI lifecycle ----------

        public function as_populate():void {
            // no-op; Python pushes initial state via as_setSize / as_setPosition
        }

        public function as_dispose():void {
            if (stage != null) {
                stage.removeEventListener(MouseEvent.MOUSE_MOVE, _onStageMouseMove);
                stage.removeEventListener(MouseEvent.MOUSE_UP,   _onStageMouseUp);
            }
            _header.removeEventListener(MouseEvent.MOUSE_DOWN, _onHeaderDown);
            _autoBox.removeEventListener(MouseEvent.CLICK, _onAutoPickClick);
            _detachRowListeners();
        }

        // ---------- Python -> AS3 setters ----------

        public function as_setSize(w:Number, h:Number):void {
            _w = w; _h = h;
            _redraw();
            _layout();
        }

        public function as_setPosition(px:Number, py:Number):void {
            if (stage != null) {
                var maxX:Number = Math.max(0, stage.stageWidth  - _w);
                var maxY:Number = Math.max(0, stage.stageHeight - _h);
                px = Math.max(0, Math.min(px, maxX));
                py = Math.max(0, Math.min(py, maxY));
            }
            this.x = px;
            this.y = py;
        }

        public function as_setEnemies(vids:Array, labels:Array, classCodes:Array):void {
            _vids       = vids       != null ? vids       : [];
            _labels     = labels     != null ? labels     : [];
            _classCodes = classCodes != null ? classCodes : [];
            _rebuildEnemyRows();
            _layout();
        }

        public function as_setSelected(vid:Number, name:String, vr:Number):void {
            _selVid  = vid;
            _selName = name != null ? name : '';
            _selVr   = vr;
            _updateTargetLine();
            _highlightSelectedRow();
        }

        public function as_setToggles(r:Boolean, b:Boolean, rs:Boolean, d:Boolean, fu:Boolean):void {
            _tRations    = r;
            _tBIA        = b;
            _tReconSit   = rs;
            _tDirectives = d;
            _tFieldUpgr  = fu;
            _refreshToggleCheckboxes();
        }

        public function as_setAutoPick(enabled:Boolean):void {
            _autoPick = enabled;
            _paintCheckbox(_autoBox, enabled);
        }

        // ---------- Python -> AS3 getters / consume-on-read ----------

        public function as_getX():Number { return this.x; }
        public function as_getY():Number { return this.y; }

        public function as_consumeSelectedVid():Number {
            var v:Number = _pendingVid;
            _pendingVid = 0;
            return v;
        }

        public function as_consumeToggleName():String {
            var n:String = _pendingToggle;
            _pendingToggle = '';
            return n;
        }

        public function as_consumeAutoPickClick():Boolean {
            var was:Boolean = _pendingAutoClick;
            _pendingAutoClick = false;
            return was;
        }

        public function as_consumeDragEnd():Boolean {
            var was:Boolean = _pendingDragEnd;
            _pendingDragEnd = false;
            return was;
        }

        // ===========================================================
        // Drawing & layout
        // ===========================================================

        private function _redraw():void {
            var g:* = _bg.graphics;
            g.clear();
            g.beginFill(COLOR_BG, ALPHA_BG);
            g.lineStyle(1, COLOR_BORDER, 0.9);
            g.drawRoundRect(0, 0, _w, _h, 8, 8);
            g.endFill();

            // Header background
            var hg:* = _header.graphics;
            hg.clear();
            hg.beginFill(COLOR_BG_HEADER, 1.0);
            hg.drawRoundRectComplex(0, 0, _w, HEADER_H, 8, 8, 0, 0);
            hg.endFill();
        }

        private function _layout():void {
            _headerLabel.x = PAD_X;
            _headerLabel.y = (HEADER_H - _headerLabel.height) / 2;

            // Content starts below header
            _content.x = 0;
            _content.y = HEADER_H;

            var y:Number = PAD_Y;

            _targetText.x = PAD_X;
            _targetText.y = y;
            y += ROW_H;

            _autoBox.x   = PAD_X;
            _autoBox.y   = y + (ROW_H - CHECKBOX_SIZE) / 2;
            _autoLabel.x = PAD_X + CHECKBOX_SIZE + 6;
            _autoLabel.y = y;
            y += ROW_H + SECTION_GAP;

            _toggleHeader.x = PAD_X;
            _toggleHeader.y = y;
            y += ROW_H;

            _toggleRow1.x = PAD_X;
            _toggleRow1.y = y;
            y += ROW_H;
            _toggleRow2.x = PAD_X;
            _toggleRow2.y = y;
            y += ROW_H + SECTION_GAP;

            _listHeader.x = PAD_X;
            _listHeader.y = y;
            y += ROW_H;

            _rowsContainer.x = PAD_X;
            _rowsContainer.y = y;
        }

        // ===========================================================
        // Header drag-handle (whole panel moves)
        // ===========================================================

        private function _onHeaderDown(e:MouseEvent):void {
            if (stage == null) return;
            _dragStartMX = stage.mouseX;
            _dragStartMY = stage.mouseY;
            _dragOffX = stage.mouseX - this.x;
            _dragOffY = stage.mouseY - this.y;
            _dragging = false;
            stage.addEventListener(MouseEvent.MOUSE_MOVE, _onStageMouseMove);
            stage.addEventListener(MouseEvent.MOUSE_UP,   _onStageMouseUp);
        }

        private function _onStageMouseMove(e:MouseEvent):void {
            if (stage == null) return;
            var dx:Number = stage.mouseX - _dragStartMX;
            var dy:Number = stage.mouseY - _dragStartMY;
            if (!_dragging && (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD)) {
                _dragging = true;
            }
            if (_dragging) {
                var nx:Number = stage.mouseX - _dragOffX;
                var ny:Number = stage.mouseY - _dragOffY;
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
                _pendingDragEnd = true;
            }
            // Header is not a click-target; no event fired on plain header click.
        }

        // ===========================================================
        // Checkbox rendering / event helpers
        // ===========================================================

        private function _makeCheckbox(initial:Boolean):Sprite {
            var s:Sprite = new Sprite();
            s.buttonMode = true;
            s.useHandCursor = true;
            s.mouseChildren = false;
            _paintCheckbox(s, initial);
            return s;
        }

        private function _paintCheckbox(s:Sprite, on:Boolean):void {
            var g:* = s.graphics;
            g.clear();
            g.beginFill(on ? COLOR_CHECK_ON : COLOR_CHECK_OFF, 1.0);
            g.lineStyle(1, COLOR_BORDER, 0.9);
            g.drawRoundRect(0, 0, CHECKBOX_SIZE, CHECKBOX_SIZE, 2, 2);
            g.endFill();
            if (on) {
                // Simple inner tick: thicker line down the middle
                g.lineStyle(2, COLOR_LABEL, 1.0);
                g.moveTo(2,                CHECKBOX_SIZE * 0.55);
                g.lineTo(CHECKBOX_SIZE/2.5, CHECKBOX_SIZE - 2);
                g.lineTo(CHECKBOX_SIZE - 1, 2);
            }
        }

        private function _makeLabel(text:String, size:Number, bold:Boolean, color:uint):TextField {
            var tf:TextField = new TextField();
            tf.selectable = false;
            tf.mouseEnabled = false;
            tf.autoSize = TextFieldAutoSize.LEFT;
            var fmt:TextFormat = new TextFormat();
            fmt.font = 'Arial';
            fmt.size = size;
            fmt.bold = bold;
            fmt.color = color;
            tf.defaultTextFormat = fmt;
            tf.text = text;
            return tf;
        }

        // ===========================================================
        // Toggles row
        // ===========================================================

        // Three on row 1, two on row 2.
        private var _toggleBoxes:Object = {};   // name -> Sprite
        private var _toggleLabels:Object = {};  // name -> TextField

        private function _buildToggleRows():void {
            var order:Array = [
                ['rations',       'rations',    _toggleRow1],
                ['BIA',           'BIA',        _toggleRow1],
                ['reconSitAware', 'reconSit',   _toggleRow1],
                ['directives',    'dyrektywy',  _toggleRow2],
                ['fieldUpgrades', 'field upgr', _toggleRow2]
            ];
            for (var i:int = 0; i < order.length; i++) {
                var name:String  = order[i][0];
                var label:String = order[i][1];
                var row:Sprite   = order[i][2];
                var box:Sprite = _makeCheckbox(false);
                var lbl:TextField = _makeLabel(label, 10, false, COLOR_LABEL_DIM);
                box.name = name;  // used in click handler
                box.addEventListener(MouseEvent.CLICK, _onToggleClick);
                row.addChild(box);
                row.addChild(lbl);
                _toggleBoxes[name]  = box;
                _toggleLabels[name] = lbl;
            }
            _layoutToggleRows();
            _refreshToggleCheckboxes();
        }

        private function _layoutToggleRows():void {
            _layoutOneToggleRow(_toggleRow1, ['rations', 'BIA', 'reconSitAware']);
            _layoutOneToggleRow(_toggleRow2, ['directives', 'fieldUpgrades']);
        }

        private function _layoutOneToggleRow(row:Sprite, names:Array):void {
            var available:Number = _w - 2 * PAD_X;
            var cellW:Number     = available / names.length;
            for (var i:int = 0; i < names.length; i++) {
                var name:String = names[i] as String;
                var box:Sprite  = _toggleBoxes[name] as Sprite;
                var lbl:TextField = _toggleLabels[name] as TextField;
                if (box == null || lbl == null) continue;
                var cellX:Number = i * cellW;
                box.x = cellX;
                box.y = (ROW_H - CHECKBOX_SIZE) / 2;
                lbl.x = cellX + CHECKBOX_SIZE + 4;
                lbl.y = 0;
            }
        }

        private function _refreshToggleCheckboxes():void {
            _paintCheckbox(_toggleBoxes['rations']       as Sprite, _tRations);
            _paintCheckbox(_toggleBoxes['BIA']           as Sprite, _tBIA);
            _paintCheckbox(_toggleBoxes['reconSitAware'] as Sprite, _tReconSit);
            _paintCheckbox(_toggleBoxes['directives']    as Sprite, _tDirectives);
            _paintCheckbox(_toggleBoxes['fieldUpgrades'] as Sprite, _tFieldUpgr);
        }

        private function _onToggleClick(e:MouseEvent):void {
            e.stopPropagation();
            var s:Sprite = e.currentTarget as Sprite;
            if (s == null) return;
            _pendingToggle = s.name;
        }

        private function _onAutoPickClick(e:MouseEvent):void {
            e.stopPropagation();
            _pendingAutoClick = true;
        }

        // ===========================================================
        // Target line + enemy rows
        // ===========================================================

        private function _updateTargetLine():void {
            if (_selVid <= 0) {
                _targetText.text = 'Target: --  VR=--m';
            } else {
                var vrTxt:String = (_selVr > 0) ? (Math.round(_selVr).toString() + 'm') : '--m';
                _targetText.text = 'Target: ' + _selName + '  VR=' + vrTxt;
            }
        }

        // Holds {bg:Shape, label:TextField, vid:Number} per row
        private var _rows:Array = [];

        private function _detachRowListeners():void {
            for (var i:int = 0; i < _rows.length; i++) {
                var row:Sprite = _rows[i].bg as Sprite;
                if (row != null) {
                    row.removeEventListener(MouseEvent.CLICK,     _onRowClick);
                    row.removeEventListener(MouseEvent.ROLL_OVER, _onRowOver);
                    row.removeEventListener(MouseEvent.ROLL_OUT,  _onRowOut);
                }
            }
        }

        private function _rebuildEnemyRows():void {
            _detachRowListeners();
            while (_rowsContainer.numChildren > 0) {
                _rowsContainer.removeChildAt(0);
            }
            _rows = [];

            var count:int = Math.min(_vids.length, MAX_ENEMY_ROWS);
            var rowW:Number = _w - 2 * PAD_X;
            for (var i:int = 0; i < count; i++) {
                var vid:Number    = Number(_vids[i]);
                var label:String  = String(_labels[i] != null ? _labels[i] : '');
                var classCode:String = String(_classCodes[i] != null ? _classCodes[i] : '');

                var row:Sprite = new Sprite();
                row.buttonMode = true;
                row.useHandCursor = true;
                row.mouseChildren = false;
                row.name = String(vid);  // stash vid as name for handler

                // Row background - transparent unless selected/hovered
                var bg:Shape = new Shape();
                row.addChild(bg);

                var tf:TextField = _makeLabel(_formatRow(classCode, label), 10, false, COLOR_LABEL);
                row.addChild(tf);
                tf.x = 4;
                tf.y = 0;

                row.y = i * ROW_H;
                _drawRowBg(bg, rowW, vid == _selVid, false);

                row.addEventListener(MouseEvent.CLICK,     _onRowClick);
                row.addEventListener(MouseEvent.ROLL_OVER, _onRowOver);
                row.addEventListener(MouseEvent.ROLL_OUT,  _onRowOut);

                _rowsContainer.addChild(row);
                _rows.push({ bg: row, shape: bg, vid: vid });
            }
        }

        private function _formatRow(classCode:String, label:String):String {
            if (classCode != null && classCode.length > 0) {
                return '[' + classCode + '] ' + label;
            }
            return label;
        }

        private function _drawRowBg(bg:Shape, w:Number, picked:Boolean, hover:Boolean):void {
            var g:* = bg.graphics;
            g.clear();
            if (picked) {
                g.beginFill(COLOR_ROW_PICKED, 0.8);
                g.drawRoundRect(0, 0, w, ROW_H, 3, 3);
                g.endFill();
            } else if (hover) {
                g.beginFill(COLOR_ROW_HOVER, 0.6);
                g.drawRoundRect(0, 0, w, ROW_H, 3, 3);
                g.endFill();
            }
            // else: transparent
        }

        private function _highlightSelectedRow():void {
            var rowW:Number = _w - 2 * PAD_X;
            for (var i:int = 0; i < _rows.length; i++) {
                var entry:Object = _rows[i];
                _drawRowBg(entry.shape as Shape, rowW, entry.vid == _selVid, false);
            }
        }

        private function _onRowClick(e:MouseEvent):void {
            e.stopPropagation();
            var s:Sprite = e.currentTarget as Sprite;
            if (s == null) return;
            var vid:Number = Number(s.name);
            if (!isNaN(vid) && vid > 0) {
                _pendingVid = vid;
            }
        }

        private function _onRowOver(e:MouseEvent):void {
            var s:Sprite = e.currentTarget as Sprite;
            if (s == null) return;
            for (var i:int = 0; i < _rows.length; i++) {
                if (_rows[i].bg === s) {
                    _drawRowBg(_rows[i].shape as Shape, _w - 2 * PAD_X,
                               _rows[i].vid == _selVid, true);
                    return;
                }
            }
        }

        private function _onRowOut(e:MouseEvent):void {
            var s:Sprite = e.currentTarget as Sprite;
            if (s == null) return;
            for (var i:int = 0; i < _rows.length; i++) {
                if (_rows[i].bg === s) {
                    _drawRowBg(_rows[i].shape as Shape, _w - 2 * PAD_X,
                               _rows[i].vid == _selVid, false);
                    return;
                }
            }
        }
    }
}
