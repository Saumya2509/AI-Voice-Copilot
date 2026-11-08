// Menu and item classes, loaded once and shared (call desk uses them for stations and colours).
import { create } from "zustand";
import { api } from "./api";
import type { ItemClass, ItemStat, MenuItem } from "./types";

interface Catalog {
  menu: Record<number, MenuItem>;
  stats: Record<number, ItemStat>;
  restaurantName: string;
  loaded: boolean;
  error: string | null;
  load: () => Promise<void>;
  classOf: (id: number | null | undefined) => ItemClass | null;
}

export const useCatalog = create<Catalog>((set, get) => ({
  menu: {},
  stats: {},
  restaurantName: "",
  loaded: false,
  error: null,
  load: async () => {
    try {
      const [menu, stats, settings] = await Promise.all([api.menu(), api.statsItems(30), api.settings()]);
      set({
        menu: Object.fromEntries(menu.items.map((m) => [m.id, m])),
        stats: Object.fromEntries(stats.items.map((s) => [s.item_id, s])),
        restaurantName: settings.restaurant_name,
        loaded: true,
        error: null,
      });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e) });
    }
  },
  classOf: (id) => (id ? get().stats[id]?.class ?? null : null),
}));
