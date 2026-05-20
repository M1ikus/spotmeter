// Compile-time stub of WG's net.wg.infrastructure.base.AbstractView.
// Subclassed by our SpotMeter* views so they satisfy the framework's
// `is IView` runtime check (via the IView stub interface in this
// package tree). At runtime AVM2 resolves AbstractView to WG's real
// class loaded into the lobby/battle ApplicationDomain, so our
// constructors / configUI / onPopulate / onDispose calls dispatch
// through the real WG base.
//
// Inherits from MovieClip so we can keep `addChild(...)`, `graphics`
// access, and our existing drag/click event listeners. The runtime
// class also extends MovieClip (via scaleform.clik.core.UIComponent),
// so the slot table is compatible.
package net.wg.infrastructure.base {
    import flash.display.MovieClip;
    import net.wg.infrastructure.interfaces.IView;

    public class AbstractView extends MovieClip implements IView {

        public function AbstractView() {
            super();
        }

        protected function configUI():void {
        }

        protected function onPopulate():void {
        }

        protected function onDispose():void {
        }
    }
}
