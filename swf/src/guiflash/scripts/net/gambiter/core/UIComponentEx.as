package net.gambiter.core
{
   import flash.display.InteractiveObject;
   import flash.events.MouseEvent;
   import net.gambiter.FlashUI;
   import net.gambiter.utils.Align;
   import net.gambiter.utils.Properties;
   import net.wg.data.constants.DragType;
   import net.wg.infrastructure.interfaces.entity.IDraggable;
   import scaleform.clik.core.UIComponent;
   
   public class UIComponentEx extends UIComponent implements IDraggable
   {
      
      protected var borderEx:UIBorderEx;
      
      public var _x:Number;
      
      public var _y:Number;
      
      private var _autoSize:Boolean;
      
      private var _alignX:String;
      
      private var _alignY:String;
      
      private var _drag:Boolean;
      
      private var _limit:Boolean;
      
      private var _isDragging:Boolean;
      
      private var _border:Boolean;
      
      private var _tooltip:String;
      
      private var _alias:String;
      
      private var _index:Number;
      
      private var _visible:Boolean;
      
      private var _radialMenu:Boolean;
      
      private var _fullStats:Boolean;
      
      private var _fullStatsQuestProgress:Boolean;
      
      private var _fullStatsPersonalReserves:Boolean;
      
      private var _epicMapOverlayVisible:Boolean;
      
      private var _epicRespawnOverlayVisible:Boolean;
      
      private var _battleRoyaleRespawnVisibility:Boolean;
      
      private var _killCamVisibility:Boolean;
      
      public function UIComponentEx()
      {
         super();
         this.borderEx = new UIBorderEx();
         addChild(this.borderEx);
         this._x = 0;
         this._y = 0;
         this._drag = false;
         this._limit = true;
         this._border = false;
         this._autoSize = true;
         this._isDragging = false;
         this._alignX = Align.LEFT;
         this._alignY = Align.TOP;
         this._visible = true;
         this._radialMenu = false;
         this._fullStats = false;
         this._fullStatsQuestProgress = false;
         this._fullStatsPersonalReserves = false;
         this._epicMapOverlayVisible = false;
         this._epicRespawnOverlayVisible = false;
         this._battleRoyaleRespawnVisibility = false;
         this._killCamVisibility = false;
         focusable = false;
      }
      
      override protected function configUI() : void
      {
         super.configUI();
         addEventListener(MouseEvent.MOUSE_OVER,this.onMouseOver,false,0,true);
         addEventListener(MouseEvent.MOUSE_OUT,this.onMouseOut,false,0,true);
      }
      
      override protected function onDispose() : void
      {
         if(this._drag)
         {
            App.cursor.unRegisterDragging(this);
         }
         removeEventListener(MouseEvent.MOUSE_OVER,this.onMouseOver);
         removeEventListener(MouseEvent.MOUSE_OUT,this.onMouseOut);
         super.onDispose();
      }
      
      override protected function draw() : void
      {
         super.draw();
      }
      
      public function refresh() : void
      {
         this.updateVisible();
         this.updateIndex();
         this.updateSize();
         this.updateBorder();
         this.updatePosition();
      }
      
      public function updateVisible() : void
      {
         super.visible = this._visible && (!FlashUI.ui.showRadialMenu || this._radialMenu) && (!FlashUI.ui.showFullStats || this._fullStats) && (!FlashUI.ui.showFullStatsQuestProgress || this._fullStatsQuestProgress) && (!FlashUI.ui.showFullStatsPersonalReserves || this._fullStatsPersonalReserves) && (!FlashUI.ui.epicMapOverlayVisibility || this._epicMapOverlayVisible) && (!FlashUI.ui.epicRespawnOverlayVisibility || this._epicRespawnOverlayVisible) && (!FlashUI.ui.battleRoyaleRespawnVisibility || this._battleRoyaleRespawnVisibility) && (!FlashUI.ui.killCamVisibility || this._killCamVisibility);
      }
      
      private function updateIndex() : void
      {
         if(!isNaN(this._index) && this._index != parent.getChildIndex(this))
         {
            parent.setChildIndex(this,Math.min(this._index,parent.numChildren - 1));
         }
      }
      
      protected function updateSize() : void
      {
      }
      
      protected function updateBorder() : void
      {
      }
      
      public function updatePosition() : void
      {
         super.x = Math.round(this._x + (parent.width - width) * Align.getFactor(this._alignX));
         super.y = Math.round(this._y + (parent.height - height) * Align.getFactor(this._alignY));
         if(!this._limit)
         {
            return;
         }
         var _loc1_:Object = Properties.getLimiter(this,super.x,super.y);
         super.x = _loc1_.x;
         super.y = _loc1_.y;
      }
      
      private function updateProps() : void
      {
         var _loc1_:Number = this._x;
         var _loc2_:Number = this._y;
         this._x = Math.round(super.x - (parent.width - width) * Align.getFactor(this._alignX));
         this._y = Math.round(super.y - (parent.height - height) * Align.getFactor(this._alignY));
         if(this._x != _loc1_ || this._y != _loc2_)
         {
            this.py_updateProps({
               "x":this._x,
               "y":this._y
            });
         }
      }
      
      private function py_updateProps(param1:Object) : void
      {
         FlashUI.ui.py_update(this.alias,param1);
      }
      
      public function hideCursor() : void
      {
         App.toolTipMgr.hide();
         this.borderEx.hide();
         this.onEndDrag();
      }
      
      private function onMouseOver(param1:MouseEvent) : void
      {
         if(!FlashUI.ui.showCursor)
         {
            return;
         }
         if(Boolean(this._tooltip) && !this._isDragging)
         {
            App.toolTipMgr.show(this._tooltip);
         }
         if(this._border)
         {
            this.borderEx.show();
         }
      }
      
      private function onMouseOut(param1:MouseEvent) : void
      {
         if(!this._drag)
         {
            return;
         }
         if(this._tooltip)
         {
            App.toolTipMgr.hide();
         }
         if(this._border)
         {
            this.borderEx.hide();
         }
      }
      
      public function getHitArea() : InteractiveObject
      {
         return this;
      }
      
      public function getDragType() : String
      {
         return DragType.SOFT;
      }
      
      public function onDragging(param1:Number, param2:Number) : void
      {
      }
      
      public function onStartDrag() : void
      {
         if(!FlashUI.ui.showCursor)
         {
            return;
         }
         if(!this._drag)
         {
            return;
         }
         this._isDragging = true;
         if(this._limit)
         {
            startDrag(false,Properties.getBound(this));
         }
         else
         {
            startDrag();
         }
         App.toolTipMgr.hide();
      }
      
      public function onEndDrag() : void
      {
         if(!this._isDragging)
         {
            return;
         }
         this._isDragging = false;
         stopDrag();
         this.updateProps();
      }
      
      public function get drag() : Boolean
      {
         return this._drag;
      }
      
      public function set drag(param1:Boolean) : void
      {
         if(param1 != this._drag)
         {
            if(param1)
            {
               App.cursor.registerDragging(this);
            }
            else
            {
               App.cursor.unRegisterDragging(this);
            }
            this._drag = param1;
         }
      }
      
      public function get limit() : Boolean
      {
         return this._limit;
      }
      
      public function set limit(param1:Boolean) : void
      {
         if(param1 != this._limit)
         {
            this._limit = param1;
         }
      }
      
      public function get tooltip() : String
      {
         return this._tooltip;
      }
      
      public function set tooltip(param1:String) : void
      {
         if(param1 != this._tooltip)
         {
            this._tooltip = param1;
         }
      }
      
      public function get alias() : String
      {
         return this._alias;
      }
      
      public function set alias(param1:String) : void
      {
         if(param1 != this._alias)
         {
            this._alias = param1;
         }
      }
      
      public function get border() : Boolean
      {
         return this._border;
      }
      
      public function set border(param1:Boolean) : void
      {
         if(param1 != this._border)
         {
            this._border = param1;
         }
      }
      
      public function get index() : Number
      {
         return this._index;
      }
      
      public function set index(param1:Number) : void
      {
         if(param1 != this._index)
         {
            this._index = param1;
         }
      }
      
      public function get alignX() : String
      {
         return this._alignX;
      }
      
      public function set alignX(param1:String) : void
      {
         if(Align.isValidX(param1) && param1 != this._alignX)
         {
            this._alignX = param1;
         }
      }
      
      public function get alignY() : String
      {
         return this._alignY;
      }
      
      public function set alignY(param1:String) : void
      {
         if(Align.isValidY(param1) && param1 != this._alignY)
         {
            this._alignY = param1;
         }
      }
      
      public function get autoSize() : Boolean
      {
         return this._autoSize;
      }
      
      public function set autoSize(param1:Boolean) : void
      {
         if(param1 != this._autoSize)
         {
            this._autoSize = param1;
         }
      }
      
      override public function set width(param1:Number) : void
      {
         this._autoSize = false;
         super.width = param1;
      }
      
      public function setLabelSizes(param1:Number, param2:Number) : void
      {
         super.width = param1;
         super.height = param2;
      }
      
      override public function set height(param1:Number) : void
      {
         this._autoSize = false;
         super.height = param1;
      }
      
      override public function set x(param1:Number) : void
      {
         this._x = param1;
      }
      
      override public function set y(param1:Number) : void
      {
         this._y = param1;
      }
      
      override public function set visible(param1:Boolean) : void
      {
         this._visible = param1;
      }
      
      public function get radialMenu() : Boolean
      {
         return this._radialMenu;
      }
      
      public function set radialMenu(param1:Boolean) : void
      {
         if(param1 != this._radialMenu)
         {
            this._radialMenu = param1;
         }
      }
      
      public function get fullStats() : Boolean
      {
         return this._fullStats;
      }
      
      public function set fullStats(param1:Boolean) : void
      {
         if(param1 != this._fullStats)
         {
            this._fullStats = param1;
         }
      }
      
      public function get fullStatsQuestProgress() : Boolean
      {
         return this._fullStatsQuestProgress;
      }
      
      public function set fullStatsQuestProgress(param1:Boolean) : void
      {
         if(param1 != this._fullStatsQuestProgress)
         {
            this._fullStatsQuestProgress = param1;
         }
      }
      
      public function get fullStatsPersonalReserves() : Boolean
      {
         return this._fullStatsPersonalReserves;
      }
      
      public function set fullStatsPersonalReserves(param1:Boolean) : void
      {
         if(param1 != this._fullStatsPersonalReserves)
         {
            this._fullStatsPersonalReserves = param1;
         }
      }
      
      public function get killCamVisibility() : Boolean
      {
         return this._killCamVisibility;
      }
      
      public function set killCamVisibility(param1:Boolean) : void
      {
         if(param1 != this._killCamVisibility)
         {
            this._killCamVisibility = param1;
         }
      }
   }
}

