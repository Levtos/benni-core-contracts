import { mount, unmount } from "svelte";
import App from "./app/App.svelte";
import { CoreContractsStore } from "./lib/core-contracts/store.svelte";
import type { HassLike } from "./lib/core-contracts/types";
import "./styles/global.css";

class BenniCoreContractsPanel extends HTMLElement {
  private readonly store = new CoreContractsStore();
  private app: ReturnType<typeof mount> | null = null;
  private currentHass: HassLike | null = null;

  connectedCallback(): void {
    if (!this.app) this.app = mount(App, { target: this, props: { store: this.store } });
    if (this.currentHass) this.store.setHass(this.currentHass);
  }

  disconnectedCallback(): void {
    if (this.app) {
      unmount(this.app);
      this.app = null;
    }
    this.store.stop();
  }

  set hass(value: HassLike | null) {
    this.currentHass = value;
    this.store.setHass(value);
  }

  get hass(): HassLike | null {
    return this.currentHass;
  }
}

if (!customElements.get("benni-core-contracts-panel")) {
  customElements.define("benni-core-contracts-panel", BenniCoreContractsPanel);
}

const devTarget = document.getElementById("app");
if (devTarget) {
  const previewStore = new CoreContractsStore();
  mount(App, { target: devTarget, props: { store: previewStore } });
}
