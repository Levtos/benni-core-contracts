import type { Component } from "svelte";

export type NavItem = {
  id: string;
  label: string;
  hint: string;
  icon: Component<{ size?: number; strokeWidth?: number }>;
};
