/* ============================================================
   BLOCKHAVEN — procedural world, lighting and serialization
   ============================================================ */
(function () {
  "use strict";
  const BH = window.BH;
  const T = BH.T;
  const W = BH.W, H = BH.H;

  class World {
    constructor(seedString) {
      this.seedString = String(seedString || "blockhaven");
      this.seed = BH.hashString(this.seedString);
      this.tiles = new Uint8Array(W * H);
      this.original = new Uint8Array(W * H);
      this.sky = new Uint8Array(W * H);
      this.blockLight = new Uint8Array(W * H);
      this.heights = new Uint8Array(W);
      this.biomes = new Uint8Array(W);
      this.changes = new Map();
      this.lightDirty = true;
      this.spawnX = W / 2 + 0.5;
      this.spawnY = 80;
      this.generate();
      this.recomputeLight();
    }

    idx(x, y) { return y * W + x; }

    get(x, y) {
      x |= 0; y |= 0;
      if (x < 0 || x >= W) return T.BEDROCK;
      if (y < 0) return T.AIR;
      if (y >= H) return T.BEDROCK;
      return this.tiles[y * W + x];
    }

    getDef(x, y) { return BH.TILE_DEFS[this.get(x, y)] || BH.TILE_DEFS[0]; }

    isSolid(x, y) {
      const d = BH.TILE_DEFS[this.get(x, y)];
      return !!(d && d.solid);
    }

    isOpaque(x, y) {
      const d = BH.TILE_DEFS[this.get(x, y)];
      return !!(d && d.opacity >= 15);
    }

    set(x, y, id, record) {
      x |= 0; y |= 0;
      if (x < 0 || x >= W || y < 0 || y >= H) return false;
      const i = y * W + x;
      if (this.tiles[i] === id) return false;
      this.tiles[i] = id;
      if (record !== false) {
        if (id === this.original[i]) this.changes.delete(i);
        else this.changes.set(i, id);
      }
      this.lightDirty = true;
      return true;
    }

    setOriginal(x, y, id) {
      const i = y * W + x;
      this.tiles[i] = id;
      this.original[i] = id;
    }

    biomeAt(x) {
      x = BH.clamp(Math.floor(x), 0, W - 1);
      return ["Meadow", "Forest", "Desert"][this.biomes[x]] || "Meadow";
    }

    /** Highest solid terrain tile in a column (cached generation height). */
    groundAt(x) {
      x = BH.clamp(Math.floor(x), 0, W - 1);
      return this.heights[x];
    }

    surfaceForSpawn(x) {
      x = BH.clamp(Math.floor(x), 0, W - 1);
      for (let y = 0; y < H; y++) {
        if (this.isSolid(x, y)) return y;
      }
      return 80;
    }

    // ---------------- generation ----------------
    generate() {
      const seed = this.seed;
      const rng = BH.mulberry32(seed ^ 0x9e3779b9);

      // 1. Continent shape and topsoil
      for (let x = 0; x < W; x++) {
        const broad = BH.noise1(x * 0.006, seed + 11);
        const mid = BH.noise1(x * 0.036, seed + 29);
        const detail = BH.noise1(x * 0.135, seed + 47);
        const ridge = BH.smoothstep(0.58, 0.84, BH.noise1(x * 0.0042, seed + 61));
        const phase = (seed % 10000) / 10000 * Math.PI * 2;
        const desertN = 0.5 + Math.sin(x * 0.012 + phase) * 0.26 +
                        (BH.noise1(x * 0.028, seed + 131) - 0.5) * 0.28;
        const forestN = 0.5 + Math.sin(x * 0.019 + phase * 1.7 + 1.3) * 0.20 +
                        (BH.noise1(x * 0.035, seed + 211) - 0.5) * 0.26;

        let surface = Math.round(86 - (broad - 0.5) * 44 - (mid - 0.5) * 17 - (detail - 0.5) * 4.5 - ridge * 18);
        surface = BH.clamp(surface, 40, 112);

        const desert = desertN > 0.61;
        let biome = desert ? 2 : (forestN > 0.515 ? 1 : 0);
        if (surface < 59 && !desert) biome = 1;
        this.biomes[x] = biome;
        this.heights[x] = surface;

        for (let y = 0; y < H; y++) {
          let id = T.AIR;
          if (y >= surface) {
            const depth = y - surface;
            if (y >= H - 3 || (y >= H - 2 && BH.rand2(x, y, seed + 5) > 0.42)) {
              id = T.BEDROCK;
            } else if (depth === 0) {
              id = desert ? T.SAND : T.GRASS;
            } else if (depth < 5) {
              id = desert ? T.SAND : T.DIRT;
            } else if (depth < 8 && desert) {
              id = T.SANDSTONE;
            } else {
              id = T.STONE;
            }
          }
          this.tiles[y * W + x] = id;
        }
      }

      // 2. Caves — soft noise chambers with a few long horizontal drafts
      for (let x = 1; x < W - 1; x++) {
        const surf = this.heights[x];
        for (let y = surf + 4; y < H - 4; y++) {
          if (this.tiles[y * W + x] === T.BEDROCK) continue;
          const depth = y - surf;
          const chamber = BH.fbm2(x * 0.045, y * 0.072, seed + 301, 3);
          const draft = Math.abs(BH.noise2(x * 0.016, y * 0.042, seed + 377) - 0.5);
          const deep = BH.clamp((depth - 35) / 100, 0, 0.12);
          const threshold = 0.625 - deep;
          if (chamber > threshold || (depth > 16 && draft < 0.018 && chamber > 0.48)) {
            this.tiles[y * W + x] = T.AIR;
          }
        }
      }

      // 3. Ore veins
      this.generateVeins(rng, seed);

      // 4. Gravel pockets and little surface boulders
      for (let i = 0; i < 90; i++) {
        const x = 4 + Math.floor(rng() * (W - 8));
        const surf = this.heights[x];
        const y = surf + 3 + Math.floor(rng() * Math.min(48, H - surf - 8));
        this.blob(x, y, 1 + Math.floor(rng() * 2), T.GRAVEL, rng, T.STONE, T.DIRT);
      }

      // 5. Trees and ground cover
      this.plantTrees(seed, rng);
      this.plantCover(seed, rng);
      this.plantDesert(seed, rng);

      // 6. Pick a friendly spawn before the trees at the very center wrap it up
      let bestX = W >> 1;
      let bestScore = Infinity;
      for (let x = 16; x < W - 16; x++) {
        if (this.biomes[x] === 2) continue;
        if (this.isSolid(x, this.heights[x] - 1)) continue;
        let slope = 0;
        for (let k = -2; k <= 2; k++) {
          slope += Math.abs(this.heights[x + k] - this.heights[x]);
          if (k !== 0 && this.isSolid(x + k, this.heights[x + k] - 1)) slope += 7;
        }
        const score = slope + Math.abs(x - (W >> 1)) * 0.055;
        if (score < bestScore) { bestScore = score; bestX = x; }
      }
      if (!Number.isFinite(bestScore) || bestScore > 200) {
        bestX = W >> 1;
        // A world with an unlucky all-desert roll still gets an oasis to start in.
        for (let x = bestX - 3; x <= bestX + 3; x++) {
          const gy = this.heights[x];
          this.tiles[gy * W + x] = T.GRASS;
          this.tiles[(gy - 1) * W + x] = T.AIR;
          this.tiles[(gy - 2) * W + x] = T.AIR;
        }
      }
      this.ensureSpawnTrees(bestX, rng);
      this.spawnX = bestX + 0.5;
      this.spawnY = this.heights[bestX];
      // Clear only the spawn column's headroom (never a full clearing), so trees
      // and canopies around the start stay natural instead of being sliced off.
      for (let y = Math.max(0, this.spawnY - 4); y < this.spawnY; y++) {
        this.tiles[y * W + bestX] = T.AIR;
      }

      // 7. border columns keep the camera inside the world
      for (const x of [0, 1, W - 2, W - 1]) {
        for (let y = this.heights[x] - 1; y < H; y++) {
          this.tiles[y * W + x] = T.BEDROCK;
        }
      }

      this.original.set(this.tiles);
      this.changes.clear();
      this.lightDirty = true;
    }

    generateVeins(rng, seed) {
      const veins = [
        { tile: T.COAL_ORE, count: 340, min: 6, max: 78, size: [3, 7] },
        { tile: T.IRON_ORE, count: 230, min: 12, max: 120, size: [2, 6] },
        { tile: T.GOLD_ORE, count: 75, min: 42, max: 155, size: [2, 5] },
        { tile: T.DIAMOND_ORE, count: 32, min: 76, max: 178, size: [1, 4] }
      ];
      for (const v of veins) {
        for (let n = 0; n < v.count; n++) {
          let x = 3 + Math.floor(rng() * (W - 6));
          let y = v.min + Math.floor(rng() * (v.max - v.min));
          const steps = v.size[0] + Math.floor(rng() * (v.size[1] - v.size[0] + 1));
          for (let s = 0; s < steps; s++) {
            if (x > 2 && x < W - 3 && y > 1 && y < H - 4) {
              const i = y * W + x;
              if (this.tiles[i] === T.STONE) this.tiles[i] = v.tile;
            }
            const dir = Math.floor(rng() * 4);
            if (dir === 0) x++;
            else if (dir === 1) x--;
            else if (dir === 2) y++;
            else y--;
          }
        }
      }
    }

    blob(cx, cy, radius, tile, rng, ...replace) {
      for (let y = cy - radius; y <= cy + radius; y++) {
        for (let x = cx - radius; x <= cx + radius; x++) {
          if (x < 2 || x >= W - 2 || y < 2 || y >= H - 3) continue;
          if ((x - cx) * (x - cx) + (y - cy) * (y - cy) > radius * radius + 1) continue;
          if (rng() < 0.14) continue;
          const current = this.tiles[y * W + x];
          if (replace.includes(current)) this.tiles[y * W + x] = tile;
        }
      }
    }

    plantTrees(seed, rng) {
      let x = 6;
      while (x < W - 6) {
        const biome = this.biomes[x];
        const y = this.heights[x];
        const chance = biome === 2 ? 0 : biome === 1 ? 0.95 : 0.7;
        if (biome !== 2 && rng() < chance && this.get(x, y) === T.GRASS) {
          this.placeTree(x, y, 4 + Math.floor(rng() * 4), rng);
        }
        x += biome === 2 ? 12 + Math.floor(rng() * 9) : biome === 1 ? 2 + Math.floor(rng() * 2) : 4 + Math.floor(rng() * 4);
      }
    }

    hasTreeNear(x, radius) {
      for (let dx = -radius; dx <= radius; dx++) {
        for (let dy = -8; dy <= 0; dy++) {
          if (this.get(x + dx, this.heights[BH.clamp(x + dx, 0, W - 1)] + dy) === T.LOG) return true;
        }
      }
      return false;
    }

    ensureSpawnTrees(centerX, rng) {
      for (const side of [-1, 1]) {
        let planted = false;
        for (let dist = 4; dist < 34; dist++) {
          const x = centerX + side * dist;
          if (x < 5 || x > W - 6 || this.biomes[x] === 2) continue;
          const y = this.heights[x];
          if (this.get(x, y) !== T.GRASS) continue;
          if (this.hasTreeNear(x, 3)) { planted = true; break; }
          this.placeTree(x, y, 5 + Math.floor(rng() * 3), rng);
          planted = true;
          break;
        }
        if (!planted) {
          // Desert fallback: a compact grassy oasis with one tree.
          for (let dist = 4; dist < 22; dist++) {
            const x = centerX + side * dist;
            if (x < 5 || x > W - 6) continue;
            const y = this.heights[x];
            if (!BH.TILE_DEFS[this.get(x, y)].solid) continue;
            for (let dx = -2; dx <= 2; dx++) {
              if (x + dx < 3 || x + dx > W - 4) continue;
              this.tiles[y * W + x + dx] = T.GRASS;
              for (let dy = 1; dy <= 4; dy++) this.tiles[(y - dy) * W + x + dx] = T.AIR;
            }
            this.placeTree(x, y, 6, rng);
            break;
          }
        }
      }
    }

    placeTree(x, groundY, height, rng) {
      const top = groundY - height;
      for (let y = groundY - 1; y >= top; y--) {
        const cur = this.get(x, y);
        if (cur === T.AIR || !BH.TILE_DEFS[cur].solid) this.tiles[y * W + x] = T.LOG;
      }
      const canopyY = top - 1;
      for (let dy = -2; dy <= 2; dy++) {
        const rad = dy <= -1 ? 2 : dy === 0 ? 2 : 1;
        for (let dx = -rad; dx <= rad; dx++) {
          if (Math.abs(dx) === rad && Math.abs(dy) === 2 && rng() < 0.55) continue;
          const lx = x + dx, ly = canopyY + dy;
          if (lx < 1 || lx >= W - 1 || ly < 1) continue;
          if (this.tiles[ly * W + lx] === T.AIR) this.tiles[ly * W + lx] = T.LEAVES;
        }
      }
      // A leafy cap
      for (let dx = -1; dx <= 1; dx++) {
        const lx = x + dx, ly = canopyY - 2;
        if (this.get(lx, ly) === T.AIR) this.tiles[ly * W + lx] = T.LEAVES;
      }
    }

    plantCover(seed, rng) {
      for (let x = 2; x < W - 2; x++) {
        const surf = this.heights[x];
        if (this.biomes[x] === 2) continue;
        if (this.get(x, surf) !== T.GRASS) continue;
        if (this.get(x, surf - 1) !== T.AIR) continue;
        const r = BH.rand2(x, 7, seed + 900);
        if (r < 0.105) this.tiles[(surf - 1) * W + x] = T.TALL_GRASS;
        else if (r < 0.128) this.tiles[(surf - 1) * W + x] = T.ROSE;
        else if (r < 0.152) this.tiles[(surf - 1) * W + x] = T.DANDELION;
      }
      // Mushrooms tucked into dark cave floors
      for (let i = 0; i < 100; i++) {
        const x = 4 + Math.floor(rng() * (W - 8));
        const y = 40 + Math.floor(rng() * (H - 46));
        if (this.get(x, y) === T.AIR && this.get(x, y + 1) === T.STONE && this.get(x, y - 1) === T.AIR) {
          this.tiles[y * W + x] = T.MUSHROOM;
        }
      }
    }

  
    plantDesert(seed, rng) {
      for (let x = 3; x < W - 3; x++) {
        if (this.biomes[x] !== 2) continue;
        const surf = this.heights[x];
        if (this.get(x, surf) !== T.SAND || this.get(x, surf - 1) !== T.AIR) continue;
        if (BH.rand2(x, 99, seed + 501) > 0.085) continue;
        const height = 1 + Math.floor(rng() * 3);
        for (let i = 0; i < height; i++) {
          if (this.get(x, surf - 1 - i) === T.AIR) this.tiles[(surf - 1 - i) * W + x] = T.CACTUS;
        }
      }
    }

  // ---------------- lighting ----------------
    recomputeLight() {
      const N = W * H;
      const sky = this.sky;
      const block = this.blockLight;
      sky.fill(0);
      block.fill(0);
      const q = [];

      // Vertical sky light. Leaves dim the column but do not stop it.
      for (let x = 0; x < W; x++) {
        let light = 15;
        for (let y = 0; y < H; y++) {
          const i = y * W + x;
          const def = BH.TILE_DEFS[this.tiles[i]];
          if (!def) continue;
          if (def.opacity >= 15) break;
          light = Math.max(0, light - def.opacity);
          if (light <= 0) break;
          sky[i] = light;
          q.push(i);
        }
      }
      this.spreadLight(sky, q);

      // Emissive blocks.
      const bq = [];
      for (let i = 0; i < N; i++) {
        const def = BH.TILE_DEFS[this.tiles[i]];
        if (!def || !def.light) continue;
        block[i] = def.light;
        bq.push(i);
      }
      this.spreadLight(block, bq);
      this.lightDirty = false;
    }

    spreadLight(arr, queue) {
      let qi = 0;
      while (qi < queue.length) {
        const i = queue[qi++];
        const level = arr[i];
        if (level <= 1) continue;
        const x = i % W;
        const y = (i / W) | 0;
        const sides = [
          x > 0 ? i - 1 : -1,
          x < W - 1 ? i + 1 : -1,
          y > 0 ? i - W : -1,
          y < H - 1 ? i + W : -1
        ];
        for (let k = 0; k < 4; k++) {
          const ni = sides[k];
          if (ni < 0) continue;
          const def = BH.TILE_DEFS[this.tiles[ni]];
          if (!def || def.opacity >= 15) continue;
          const next = level - 1 - def.opacity;
          if (next > arr[ni]) {
            arr[ni] = next;
            queue.push(ni);
          }
        }
      }
    }

    /** Soft maximum of nearby light, so surfaces in a lit room are visible. */
    lightAt(x, y, skyFactor) {
      let skyL = 0, blockL = 0;
      for (let dy = -1; dy <= 1; dy++) {
        for (let dx = -1; dx <= 1; dx++) {
          const i = (y + dy) * W + (x + dx);
          if (i < 0 || i >= W * H) continue;
          if (this.sky[i] > skyL) skyL = this.sky[i];
          if (this.blockLight[i] > blockL) blockL = this.blockLight[i];
        }
      }
      const s = (skyL / 15) * skyFactor;
      const b = blockL / 15;
      return Math.max(s, b);
    }

    // ---------------- persistence ----------------
    serialize() {
      const changes = [];
      this.changes.forEach((v, k) => changes.push([k, v]));
      return {
        seed: this.seedString,
        spawnX: this.spawnX,
        spawnY: this.spawnY,
        changes
      };
    }

    applySerialized(data) {
      if (!data) return;
      if (Array.isArray(data.changes)) {
        for (const pair of data.changes) {
          if (!Array.isArray(pair) || pair.length < 2) continue;
          const i = pair[0] | 0;
          const id = pair[1] | 0;
          if (i < 0 || i >= W * H || !BH.TILE_DEFS[id]) continue;
          this.tiles[i] = id;
          if (id === this.original[i]) this.changes.delete(i);
          else this.changes.set(i, id);
        }
      }
      if (typeof data.spawnX === "number" && isFinite(data.spawnX)) this.spawnX = data.spawnX;
      if (typeof data.spawnY === "number" && isFinite(data.spawnY)) this.spawnY = data.spawnY;
      this.lightDirty = true;
      this.recomputeLight();
    }
  }

  BH.World = World;
})();
