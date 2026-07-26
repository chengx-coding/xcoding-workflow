const GRAPH = {
  nodeWidth: 232,
  nodeHeight: 86,
  columnGap: 112,
  rowGap: 30,
  padding: 42,
  minScale: 0.25,
  maxScale: 1.5,
  scaleStep: 0.1,
};

const state = {
  clientId: null,
  selectedTreeId: null,
  selectedNodeId: null,
  snapshotVersion: null,
  currentSnapshot: null,
  heartbeatTimer: null,
  refreshTimer: null,
  collapsedByTree: new Map(),
  scaleByTree: new Map(),
  graphSize: { width: 0, height: 0 },
};

const elements = {
  treeSelect: document.querySelector("#tree-select"),
  refreshButton: document.querySelector("#refresh-button"),
  registerForm: document.querySelector("#register-form"),
  treePath: document.querySelector("#tree-path"),
  message: document.querySelector("#message"),
  serverStatus: document.querySelector("#server-status"),
  overview: document.querySelector("#overview"),
  runName: document.querySelector("#run-name"),
  runId: document.querySelector("#run-id"),
  runStatus: document.querySelector("#run-status"),
  integrityStatus: document.querySelector("#integrity-status"),
  graphViewport: document.querySelector("#graph-viewport"),
  graphSizer: document.querySelector("#graph-sizer"),
  graphStage: document.querySelector("#graph-stage"),
  graphEdges: document.querySelector("#graph-edges"),
  graphNodes: document.querySelector("#graph-nodes"),
  graphEmpty: document.querySelector("#graph-empty"),
  expandAllButton: document.querySelector("#expand-all-button"),
  collapseAllButton: document.querySelector("#collapse-all-button"),
  zoomOutButton: document.querySelector("#zoom-out-button"),
  zoomResetButton: document.querySelector("#zoom-reset-button"),
  zoomInButton: document.querySelector("#zoom-in-button"),
  fitButton: document.querySelector("#fit-button"),
  nodeDetail: document.querySelector("#node-detail"),
  blackboard: document.querySelector("#blackboard"),
  nodeTemplate: document.querySelector("#node-template"),
};

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error?.message || `Request failed: ${response.status}`);
  }
  return payload;
}

function setMessage(message, isError = false) {
  elements.message.textContent = message || "";
  elements.message.classList.toggle("error", isError);
}

function statusClass(status) {
  return `status-${String(status || "unknown").replace(/[^a-z0-9-]/gi, "-")}`;
}

function collapsedNodes() {
  if (!state.selectedTreeId) {
    return new Set();
  }
  if (!state.collapsedByTree.has(state.selectedTreeId)) {
    state.collapsedByTree.set(state.selectedTreeId, new Set());
  }
  return state.collapsedByTree.get(state.selectedTreeId);
}

function currentScale() {
  return state.scaleByTree.get(state.selectedTreeId) || 1;
}

function selectTree(treeId) {
  state.selectedTreeId = treeId || null;
  state.snapshotVersion = null;
  state.selectedNodeId = null;
  state.currentSnapshot = null;
  if (treeId) {
    elements.treeSelect.value = treeId;
  }
  refreshSnapshot();
}

function populateTrees(trees) {
  const previous = state.selectedTreeId;
  elements.treeSelect.replaceChildren();
  if (!trees.length) {
    elements.treeSelect.add(new Option("No trees registered", ""));
    state.selectedTreeId = null;
    return;
  }
  for (const tree of trees) {
    const label = `${tree.name || tree.path} (${tree.status})`;
    elements.treeSelect.add(new Option(label, tree.tree_id));
  }
  const known = trees.some((tree) => tree.tree_id === previous);
  state.selectedTreeId = known ? previous : trees[0].tree_id;
  elements.treeSelect.value = state.selectedTreeId;
}

function renderOverview(snapshot) {
  const metadata = snapshot.metadata || {};
  const integrity = snapshot.integrity || {};
  elements.overview.hidden = false;
  elements.runName.textContent = metadata.name || "Unnamed run";
  elements.runId.textContent = metadata.run_id || "n/a";
  elements.runStatus.textContent = metadata.status || "unknown";
  elements.runStatus.className = statusClass(metadata.status);
  elements.integrityStatus.textContent = integrity.status || "unknown";
  elements.integrityStatus.className = statusClass(integrity.status);
  elements.blackboard.textContent = JSON.stringify(snapshot.blackboard || {}, null, 2);
}

function walkNodes(node, visitor) {
  if (!node) {
    return;
  }
  visitor(node);
  for (const child of node.children || []) {
    walkNodes(child, visitor);
  }
}

function allNodeIds(root) {
  const identifiers = new Set();
  walkNodes(root, (node) => identifiers.add(node.id));
  return identifiers;
}

function childBearingNodeIds(root) {
  const identifiers = new Set();
  walkNodes(root, (node) => {
    if (node.children?.length) {
      identifiers.add(node.id);
    }
  });
  return identifiers;
}

function countDescendants(node) {
  return (node.children || []).reduce((count, child) => count + 1 + countDescendants(child), 0);
}

function findNode(node, nodeId) {
  if (!node || !nodeId) {
    return null;
  }
  if (node.id === nodeId) {
    return node;
  }
  for (const child of node.children || []) {
    const found = findNode(child, nodeId);
    if (found) {
      return found;
    }
  }
  return null;
}

function findNodePath(node, nodeId, path = []) {
  if (!node) {
    return null;
  }
  const nextPath = [...path, node];
  if (node.id === nodeId) {
    return nextPath;
  }
  for (const child of node.children || []) {
    const found = findNodePath(child, nodeId, nextPath);
    if (found) {
      return found;
    }
  }
  return null;
}

function prunePresentationState(root) {
  const validIds = allNodeIds(root);
  const collapsibleIds = childBearingNodeIds(root);
  const collapsed = collapsedNodes();
  for (const nodeId of [...collapsed]) {
    if (!collapsibleIds.has(nodeId)) {
      collapsed.delete(nodeId);
    }
  }
  if (state.selectedNodeId && !validIds.has(state.selectedNodeId)) {
    state.selectedNodeId = null;
  }
}

function layoutGraph(root) {
  const collapsed = collapsedNodes();
  const heights = new Map();
  const visibleChildren = new Map();

  function measure(node) {
    const children = collapsed.has(node.id) ? [] : (node.children || []);
    visibleChildren.set(node.id, children);
    if (!children.length) {
      heights.set(node.id, GRAPH.nodeHeight);
      return GRAPH.nodeHeight;
    }
    const childHeight = children.reduce((total, child) => total + measure(child), 0);
    const gaps = GRAPH.rowGap * Math.max(children.length - 1, 0);
    const height = Math.max(GRAPH.nodeHeight, childHeight + gaps);
    heights.set(node.id, height);
    return height;
  }

  const rootHeight = measure(root);
  const nodes = [];
  const edges = [];
  let maxDepth = 0;

  function place(node, depth, top, parentId = null) {
    maxDepth = Math.max(maxDepth, depth);
    const subtreeHeight = heights.get(node.id);
    const position = {
      node,
      x: GRAPH.padding + depth * (GRAPH.nodeWidth + GRAPH.columnGap),
      y: GRAPH.padding + top + (subtreeHeight - GRAPH.nodeHeight) / 2,
    };
    nodes.push(position);
    if (parentId) {
      edges.push({ sourceId: parentId, targetId: node.id, status: node.status });
    }
    let childTop = top;
    for (const child of visibleChildren.get(node.id) || []) {
      place(child, depth + 1, childTop, node.id);
      childTop += heights.get(child.id) + GRAPH.rowGap;
    }
  }

  place(root, 0, 0);
  return {
    nodes,
    edges,
    width: GRAPH.padding * 2 + (maxDepth + 1) * GRAPH.nodeWidth + maxDepth * GRAPH.columnGap,
    height: GRAPH.padding * 2 + rootHeight,
  };
}

function svgElement(tag, attributes) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [name, value] of Object.entries(attributes)) {
    element.setAttribute(name, value);
  }
  return element;
}

function renderEdges(layout, positions) {
  elements.graphEdges.replaceChildren();
  elements.graphEdges.setAttribute("width", layout.width);
  elements.graphEdges.setAttribute("height", layout.height);
  elements.graphEdges.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
  for (const edge of layout.edges) {
    const source = positions.get(edge.sourceId);
    const target = positions.get(edge.targetId);
    const startX = source.x + GRAPH.nodeWidth;
    const startY = source.y + GRAPH.nodeHeight / 2;
    const endX = target.x;
    const endY = target.y + GRAPH.nodeHeight / 2;
    const controlOffset = Math.max((endX - startX) * 0.5, 36);
    const path = svgElement("path", {
      d: `M ${startX} ${startY} C ${startX + controlOffset} ${startY}, ${endX - controlOffset} ${endY}, ${endX} ${endY}`,
      class: `graph-edge edge-${statusClass(edge.status)}`,
    });
    elements.graphEdges.append(path);
  }
}

function selectNode(nodeId) {
  state.selectedNodeId = nodeId;
  renderGraph();
  renderNodeDetail(findNode(state.currentSnapshot?.root, nodeId));
}

function createGraphNode(position) {
  const { node, x, y } = position;
  const fragment = elements.nodeTemplate.content.cloneNode(true);
  const card = fragment.querySelector(".graph-node");
  const selectButton = fragment.querySelector(".node-select");
  const toggleButton = fragment.querySelector(".node-toggle");
  const title = fragment.querySelector(".node-title");
  const role = fragment.querySelector(".node-role");
  const status = fragment.querySelector(".node-status");
  const hiddenCount = fragment.querySelector(".hidden-count");
  const collapsed = collapsedNodes().has(node.id);
  const childCount = node.children?.length || 0;

  card.style.left = `${x}px`;
  card.style.top = `${y}px`;
  card.classList.add(statusClass(node.status));
  card.classList.toggle("selected", node.id === state.selectedNodeId);
  card.dataset.nodeId = node.id;

  title.textContent = node.title || node.id;
  role.textContent = [node.type, node.role].filter(Boolean).join(" / ");
  status.textContent = node.status || "unknown";
  status.className = `node-status ${statusClass(node.status)}`;
  selectButton.setAttribute("aria-label", `Select ${node.title || node.id}`);
  selectButton.addEventListener("click", () => selectNode(node.id));

  if (childCount) {
    toggleButton.textContent = collapsed ? "+" : "-";
    toggleButton.setAttribute("aria-expanded", String(!collapsed));
    toggleButton.setAttribute(
      "aria-label",
      `${collapsed ? "Expand" : "Collapse"} child nodes of ${node.title || node.id}`,
    );
    toggleButton.addEventListener("click", () => toggleNode(node));
    if (collapsed) {
      hiddenCount.textContent = `${countDescendants(node)} hidden`;
    } else {
      hiddenCount.hidden = true;
    }
  } else {
    toggleButton.hidden = true;
    hiddenCount.hidden = true;
  }
  return fragment;
}

function toggleNode(node) {
  const collapsed = collapsedNodes();
  if (collapsed.has(node.id)) {
    collapsed.delete(node.id);
  } else {
    collapsed.add(node.id);
    const selectedPath = findNodePath(node, state.selectedNodeId);
    if (selectedPath && state.selectedNodeId !== node.id) {
      state.selectedNodeId = node.id;
      renderNodeDetail(node);
    }
  }
  renderGraph();
}

function applyGraphScale(scale, center = false) {
  const normalized = Math.min(GRAPH.maxScale, Math.max(GRAPH.minScale, scale));
  state.scaleByTree.set(state.selectedTreeId, normalized);
  elements.graphStage.style.transform = `scale(${normalized})`;
  elements.graphSizer.style.width = `${Math.ceil(state.graphSize.width * normalized)}px`;
  elements.graphSizer.style.height = `${Math.ceil(state.graphSize.height * normalized)}px`;
  const percentage = Math.round(normalized * 100);
  elements.zoomResetButton.textContent = `${percentage}%`;
  elements.zoomResetButton.setAttribute("aria-label", `Reset zoom (${percentage}%)`);
  elements.zoomOutButton.disabled = normalized <= GRAPH.minScale;
  elements.zoomInButton.disabled = normalized >= GRAPH.maxScale;
  if (center) {
    elements.graphViewport.scrollTo({ left: 0, top: 0, behavior: "smooth" });
  }
}

function setZoom(scale) {
  applyGraphScale(scale);
}

function fitGraph() {
  if (!state.graphSize.width || !state.graphSize.height) {
    return;
  }
  const availableWidth = Math.max(elements.graphViewport.clientWidth - 24, 1);
  const availableHeight = Math.max(elements.graphViewport.clientHeight - 24, 1);
  const scale = Math.min(1, availableWidth / state.graphSize.width, availableHeight / state.graphSize.height);
  applyGraphScale(scale, true);
}

function renderGraph() {
  elements.graphNodes.replaceChildren();
  elements.graphEdges.replaceChildren();
  const root = state.currentSnapshot?.root;
  if (!root) {
    elements.graphEmpty.hidden = false;
    elements.graphSizer.hidden = true;
    return;
  }

  prunePresentationState(root);
  const layout = layoutGraph(root);
  const positions = new Map(layout.nodes.map((position) => [position.node.id, position]));
  state.graphSize = { width: layout.width, height: layout.height };

  elements.graphEmpty.hidden = true;
  elements.graphSizer.hidden = false;
  elements.graphStage.style.width = `${layout.width}px`;
  elements.graphStage.style.height = `${layout.height}px`;
  elements.graphNodes.style.width = `${layout.width}px`;
  elements.graphNodes.style.height = `${layout.height}px`;
  renderEdges(layout, positions);
  for (const position of layout.nodes) {
    elements.graphNodes.append(createGraphNode(position));
  }
  applyGraphScale(currentScale());
}

function renderNodeDetail(node) {
  if (!node) {
    elements.nodeDetail.textContent = "Select a node to inspect its details.";
    return;
  }
  const fields = [
    ["ID", node.id],
    ["Template ID", node.origin_template_id || node.template_id],
    ["Type", [node.type, node.role].filter(Boolean).join(" / ")],
    ["Executor", node.executor],
    ["Status", node.status],
    ["Path", (node.path || []).join(" > ")],
    ["Instructions", node.instructions],
    ["Inputs", node.inputs],
    ["Deliverables", node.deliverables],
    ["Acceptance", node.acceptance],
    ["Result", JSON.stringify(node.result || {}, null, 2)],
  ];
  elements.nodeDetail.replaceChildren();
  for (const [label, value] of fields) {
    if (!value) {
      continue;
    }
    const block = document.createElement("div");
    const heading = document.createElement("h3");
    const text = document.createElement("pre");
    heading.textContent = label;
    text.textContent = value;
    block.append(heading, text);
    elements.nodeDetail.append(block);
  }
}

function expandAll() {
  collapsedNodes().clear();
  renderGraph();
}

function collapseAll() {
  const root = state.currentSnapshot?.root;
  if (!root) {
    return;
  }
  const collapsed = collapsedNodes();
  collapsed.clear();
  for (const child of root.children || []) {
    walkNodes(child, (node) => {
      if (node.children?.length) {
        collapsed.add(node.id);
      }
    });
  }
  const selectedPath = findNodePath(root, state.selectedNodeId);
  if (selectedPath?.length > 2) {
    state.selectedNodeId = selectedPath[1].id;
    renderNodeDetail(selectedPath[1]);
  }
  renderGraph();
}

async function refreshSnapshot(force = false) {
  if (!state.selectedTreeId) {
    elements.overview.hidden = true;
    state.currentSnapshot = null;
    renderGraph();
    return;
  }
  try {
    if (force) {
      await request(`/api/trees/${encodeURIComponent(state.selectedTreeId)}/refresh`, {
        method: "POST",
        body: "{}",
      });
    }
    const payload = await request(`/api/trees/${encodeURIComponent(state.selectedTreeId)}/snapshot`);
    const snapshot = payload.snapshot;
    if (state.snapshotVersion === snapshot.version) {
      return;
    }
    state.snapshotVersion = snapshot.version;
    state.currentSnapshot = snapshot;
    renderOverview(snapshot);
    renderGraph();
    renderNodeDetail(findNode(snapshot.root, state.selectedNodeId));
    setMessage(payload.refresh_error?.message || "");
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function refreshTrees() {
  try {
    const payload = await request("/api/trees");
    const previous = state.selectedTreeId;
    populateTrees(payload.trees);
    if (state.selectedTreeId !== previous || state.snapshotVersion === null) {
      await refreshSnapshot();
    }
  } catch (error) {
    setMessage(error.message, true);
  }
}

async function connectClient() {
  try {
    const payload = await request("/api/clients", { method: "POST", body: "{}" });
    state.clientId = payload.client_id;
    elements.serverStatus.textContent = "Connected to local read-only viewer.";
    const interval = Math.max(payload.heartbeat_seconds * 500, 1000);
    state.heartbeatTimer = window.setInterval(() => {
      request(`/api/clients/${encodeURIComponent(state.clientId)}/heartbeat`, {
        method: "POST",
        body: "{}",
      }).catch(() => {
        elements.serverStatus.textContent = "Viewer connection lost.";
      });
    }, interval);
  } catch (error) {
    elements.serverStatus.textContent = `Unable to connect: ${error.message}`;
  }
}

elements.treeSelect.addEventListener("change", () => selectTree(elements.treeSelect.value));
elements.refreshButton.addEventListener("click", () => refreshSnapshot(true));
elements.expandAllButton.addEventListener("click", expandAll);
elements.collapseAllButton.addEventListener("click", collapseAll);
elements.zoomOutButton.addEventListener("click", () => setZoom(currentScale() - GRAPH.scaleStep));
elements.zoomInButton.addEventListener("click", () => setZoom(currentScale() + GRAPH.scaleStep));
elements.zoomResetButton.addEventListener("click", () => setZoom(1));
elements.fitButton.addEventListener("click", fitGraph);
elements.registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const path = elements.treePath.value.trim();
  if (!path) {
    setMessage("Enter a runtime XML path.", true);
    return;
  }
  try {
    const payload = await request("/api/trees", {
      method: "POST",
      body: JSON.stringify({ path }),
    });
    elements.treePath.value = "";
    await refreshTrees();
    selectTree(payload.tree.tree_id);
    setMessage("Tree registered.");
  } catch (error) {
    setMessage(error.message, true);
  }
});

Promise.all([connectClient(), refreshTrees()]).then(() => {
  state.refreshTimer = window.setInterval(refreshTrees, 1000);
});
