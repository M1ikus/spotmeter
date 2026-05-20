// Compile-time stub of WG's net.wg.infrastructure.interfaces.IView.
// At runtime AVM2 resolves the reference to WG's real interface
// (already loaded into the lobby/battle ApplicationDomain), so our
// `implements IView` declaration gets re-bound to the live WG class
// and the framework's `loadedView is IView` check passes.
//
// Keep this interface EMPTY. WG's real IView may declare members;
// we don't need to mirror them because the compile-time stub is
// thrown away at link time - the runtime IView is what matters.
package net.wg.infrastructure.interfaces {
    public interface IView {
    }
}
