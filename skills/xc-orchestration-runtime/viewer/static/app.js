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
const AUTO_REFRESH_MS = 20000;

const state = {
  clientId: null,
  selectedTreeId: null,
  selectedNodeId: null,
  snapshotVersion: null,
  snapshotRequestId: 0,
  currentSnapshot: null,
  heartbeatTimer: null,
  reconnectTimer: null,
  connecting: false,
  messageIsConnectionError: false,
  refreshTimer: null,
  blackboardTimer: null,
  collapsedByTree: new Map(),
  scaleByTree: new Map(),
  blackboardCollapsedByTree: new Map(),
  sidebarCollapsed: false,
  pan: null,
  resize: null,
  graphSize: { width: 0, height: 0 },
};

const elements = {
  viewerLayout: document.querySelector(".viewer-layout"),
  treeSidebar: document.querySelector("#tree-sidebar"),
  sidebarToggle: document.querySelector("#sidebar-toggle"),
  sidebarToggleIcon: document.querySelector(".sidebar-toggle-icon"),
  refreshButton: document.querySelector("#refresh-button"),
  saveSvgButton: document.querySelector("#save-svg-button"),
  registerForm: document.querySelector("#register-form"),
  pickTreeButton: document.querySelector("#pick-tree-button"),
  treePath: document.querySelector("#tree-path"),
  treeList: document.querySelector("#tree-list"),
  treeCount: document.querySelector("#tree-count"),
  message: document.querySelector("#message"),
  serverStatus: document.querySelector("#server-status"),
  serverStatusLabel: document.querySelector("#server-status-label"),
  overview: document.querySelector("#overview"),
  runName: document.querySelector("#run-name"),
  runId: document.querySelector("#run-id"),
  runStatus: document.querySelector("#run-status"),
  integrityStatus: document.querySelector("#integrity-status"),
  graphViewport: document.querySelector("#graph-viewport"),
  graphResizeHandle: document.querySelector("#graph-resize-handle"),
  graphSizer: document.querySelector("#graph-sizer"),
  graphStage: document.querySelector("#graph-stage"),
  graphEdges: document.querySelector("#graph-edges"),
  graphNodes: document.querySelector("#graph-nodes"),
  graphEmpty: document.querySelector("#graph-empty"),
  zoomSlider: document.querySelector("#zoom-slider"),
  zoomValue: document.querySelector("#zoom-value"),
  nodeDetail: document.querySelector("#node-detail"),
  blackboardPanel: document.querySelector(".blackboard-panel"),
  blackboardValues: document.querySelector("#blackboard-values"),
  blackboardUpdatedAt: document.querySelector("#blackboard-updated-at"),
  blackboardToggle: document.querySelector("#blackboard-toggle"),
  blackboardToggleIcon: document.querySelector(".blackboard-toggle-icon"),
  nodeTemplate: document.querySelector("#node-template"),
};

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch (cause) {
    const error = new Error("Viewer server is unreachable.");
    error.connectionLost = true;
    error.cause = cause;
    throw error;
  }
  let payload;
  try {
    payload = await response.json();
  } catch (cause) {
    const error = new Error("Viewer server returned an invalid response.");
    error.connectionLost = true;
    error.cause = cause;
    throw error;
  }
  if (!response.ok || !payload.ok) {
    throw new Error(payload.error?.message || `Request failed: ${response.status}`);
  }
  return payload;
}

function setConnectionStatus(status) {
  elements.serverStatus.dataset.connection = status;
  elements.serverStatusLabel.textContent = status.charAt(0).toUpperCase() + status.slice(1);
}

function clearHeartbeat() {
  if (state.heartbeatTimer !== null) {
    window.clearInterval(state.heartbeatTimer);
    state.heartbeatTimer = null;
  }
}

function scheduleReconnect() {
  if (state.reconnectTimer !== null) {
    return;
  }
  state.reconnectTimer = window.setTimeout(() => {
    state.reconnectTimer = null;
    connectClient();
  }, 2000);
}

function disconnectClient() {
  state.clientId = null;
  clearHeartbeat();
  setConnectionStatus("disconnected");
  scheduleReconnect();
}

function handleRequestFailure(error) {
  if (error.connectionLost) {
    disconnectClient();
  }
}

function setMessage(message, isError = false, isConnectionError = false) {
  elements.message.textContent = message || "";
  elements.message.classList.toggle("error", isError);
  state.messageIsConnectionError = Boolean(message && isConnectionError);
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

function blackboardIsCollapsed() {
  return state.blackboardCollapsedByTree.get(state.selectedTreeId) || false;
}

function updateTreeSelection() {
  for (const instance of elements.treeList.querySelectorAll(".tree-instance")) {
    const selected = instance.dataset.treeId === state.selectedTreeId;
    instance.classList.toggle("selected", selected);
    const select = instance.querySelector(".tree-instance-select");
    if (selected) {
      select?.setAttribute("aria-current", "true");
    } else {
      select?.removeAttribute("aria-current");
    }
  }
}

function selectTree(treeId) {
  state.selectedTreeId = treeId || null;
  updateTreeSelection();
  elements.saveSvgButton.disabled = !state.selectedTreeId;
  state.snapshotVersion = null;
  state.selectedNodeId = null;
  state.currentSnapshot = null;
  refreshSnapshot();
}

function populateTrees(trees) {
  const previous = state.selectedTreeId;
  elements.treeList.replaceChildren();
  elements.treeCount.textContent = String(trees.length);
  if (!trees.length) {
    state.selectedTreeId = null;
    elements.saveSvgButton.disabled = true;
    const empty = document.createElement("p");
    empty.className = "blackboard-empty";
    empty.textContent = "No runtime trees registered.";
    elements.treeList.append(empty);
    return;
  }
  const known = trees.some((tree) => tree.tree_id === previous);
  state.selectedTreeId = known ? previous : trees[0].tree_id;
  elements.saveSvgButton.disabled = false;
  for (const tree of trees) {
    elements.treeList.append(createTreeInstance(tree));
  }
}

function createTreeInstance(tree) {
  const instance = document.createElement("article");
  instance.className = "tree-instance";
  instance.dataset.treeId = tree.tree_id;
  instance.classList.toggle("selected", tree.tree_id === state.selectedTreeId);

  const select = document.createElement("button");
  select.className = "tree-instance-select";
  select.type = "button";
  if (tree.tree_id === state.selectedTreeId) {
    select.setAttribute("aria-current", "true");
  }
  select.setAttribute("aria-label", `Select ${tree.name || tree.path}`);
  select.addEventListener("click", () => selectTree(tree.tree_id));

  const name = document.createElement("span");
  name.className = "tree-instance-name";
  name.textContent = tree.name || tree.path;
  const status = document.createElement("span");
  status.className = `tree-instance-status ${statusClass(tree.status)}`;
  status.textContent = tree.status || "unavailable";
  const path = document.createElement("span");
  path.className = "tree-instance-path";
  path.textContent = tree.path;
  path.title = tree.path;
  select.append(name, status, path);

  const remove = document.createElement("button");
  remove.className = "tree-instance-remove";
  remove.type = "button";
  remove.textContent = "×";
  remove.setAttribute("aria-label", `Remove ${tree.name || tree.path} from this viewer`);
  remove.title = "Remove from this viewer";
  remove.addEventListener("click", () => removeTree(tree.tree_id));
  instance.append(select, remove);
  return instance;
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
  renderBlackboard(snapshot);
}

function formatUpdatedAt(value) {
  const timestamp = Date.parse(value || "");
  if (Number.isNaN(timestamp)) {
    return "Updated time unavailable";
  }
  const minutes = Math.max(0, Math.floor((Date.now() - timestamp) / 60000));
  if (minutes < 24 * 60) {
    return `Updated ${minutes} min ago`;
  }
  const date = new Date(timestamp);
  const twoDigits = (part) => String(part).padStart(2, "0");
  return `Updated ${date.getFullYear()}-${twoDigits(date.getMonth() + 1)}-${twoDigits(date.getDate())} ${twoDigits(date.getHours())}:${twoDigits(date.getMinutes())}`;
}

function renderBlackboard(snapshot = state.currentSnapshot) {
  const metadata = snapshot?.metadata || {};
  const blackboard = snapshot?.blackboard || {};
  const collapsed = blackboardIsCollapsed();
  elements.blackboardPanel.classList.toggle("collapsed", collapsed);
  elements.blackboardToggle.setAttribute("aria-expanded", String(!collapsed));
  elements.blackboardToggleIcon.textContent = collapsed ? "⌄" : "⌃";
  elements.blackboardToggle.querySelector(".sr-only").textContent = collapsed ? "Expand blackboard" : "Collapse blackboard";
  elements.blackboardUpdatedAt.textContent = formatUpdatedAt(metadata.blackboard_updated_at);
  elements.blackboardValues.replaceChildren();
  const entries = Object.entries(blackboard).sort(([left], [right]) => left.localeCompare(right));
  if (!entries.length) {
    const empty = document.createElement("p");
    empty.className = "blackboard-empty";
    empty.textContent = "No blackboard values.";
    elements.blackboardValues.append(empty);
    return;
  }
  for (const [key, value] of entries) {
    const row = document.createElement("div");
    row.className = "blackboard-row";
    const keyElement = document.createElement("code");
    keyElement.className = "blackboard-key";
    keyElement.textContent = key;
    const valueElement = document.createElement("code");
    valueElement.className = "blackboard-value";
    valueElement.textContent = value;
    row.append(keyElement, valueElement);
    elements.blackboardValues.append(row);
  }
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

function applyGraphScale(scale) {
  const normalized = Math.min(GRAPH.maxScale, Math.max(GRAPH.minScale, scale));
  state.scaleByTree.set(state.selectedTreeId, normalized);
  elements.graphStage.style.transform = `scale(${normalized})`;
  elements.graphSizer.style.width = `${Math.ceil(state.graphSize.width * normalized)}px`;
  elements.graphSizer.style.height = `${Math.ceil(state.graphSize.height * normalized)}px`;
  elements.zoomSlider.value = String(Math.round(normalized * 100));
  elements.zoomValue.value = `${Math.round(normalized * 100)}%`;
  elements.zoomValue.textContent = elements.zoomValue.value;
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

async function refreshSnapshot(force = false) {
  const treeId = state.selectedTreeId;
  const requestId = ++state.snapshotRequestId;
  if (!treeId) {
    elements.overview.hidden = true;
    state.currentSnapshot = null;
    renderGraph();
    renderNodeDetail(null);
    renderBlackboard(null);
    return;
  }
  try {
    if (force) {
      await request(`/api/trees/${encodeURIComponent(treeId)}/refresh`, {
        method: "POST",
        body: "{}",
      });
      if (requestId !== state.snapshotRequestId || treeId !== state.selectedTreeId) {
        return;
      }
    }
    const payload = await request(`/api/trees/${encodeURIComponent(treeId)}/snapshot`);
    if (requestId !== state.snapshotRequestId || treeId !== state.selectedTreeId) {
      return;
    }
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
    if (requestId !== state.snapshotRequestId || treeId !== state.selectedTreeId) {
      return;
    }
    setMessage(error.message, true, Boolean(error.connectionLost));
    handleRequestFailure(error);
  }
}

async function refreshTrees() {
  try {
    const payload = await request("/api/trees");
    const previous = state.selectedTreeId;
    populateTrees(payload.trees);
    await refreshSnapshot();
  } catch (error) {
    setMessage(error.message, true, Boolean(error.connectionLost));
    handleRequestFailure(error);
  }
}

async function removeTree(treeId) {
  try {
    await request(`/api/trees/${encodeURIComponent(treeId)}`, { method: "DELETE", body: "{}" });
    if (state.selectedTreeId === treeId) {
      state.selectedTreeId = null;
      state.snapshotVersion = null;
      state.currentSnapshot = null;
      state.selectedNodeId = null;
    }
    await refreshTrees();
    setMessage("Tree removed from this viewer.");
  } catch (error) {
    setMessage(error.message, true);
  }
}

function setSidebarCollapsed(collapsed) {
  state.sidebarCollapsed = collapsed;
  elements.treeSidebar.classList.toggle("collapsed", collapsed);
  elements.viewerLayout.classList.toggle("sidebar-collapsed", collapsed);
  elements.sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
  elements.sidebarToggleIcon.textContent = collapsed ? "›" : "‹";
  elements.sidebarToggle.querySelector(".sr-only").textContent = collapsed ? "Expand sidebar" : "Collapse sidebar";
}

function toggleBlackboard() {
  if (!state.selectedTreeId) {
    return;
  }
  state.blackboardCollapsedByTree.set(state.selectedTreeId, !blackboardIsCollapsed());
  renderBlackboard();
}

function zoomAroundPointer(event) {
  if (!state.currentSnapshot) {
    return;
  }
  event.preventDefault();
  const viewport = elements.graphViewport;
  const beforeScale = currentScale();
  const scaleDelta = event.deltaY < 0 ? GRAPH.scaleStep : -GRAPH.scaleStep;
  const afterScale = Math.min(GRAPH.maxScale, Math.max(GRAPH.minScale, beforeScale + scaleDelta));
  if (afterScale === beforeScale) {
    return;
  }
  const rect = viewport.getBoundingClientRect();
  const pointerX = event.clientX - rect.left + viewport.scrollLeft;
  const pointerY = event.clientY - rect.top + viewport.scrollTop;
  const contentX = pointerX / beforeScale;
  const contentY = pointerY / beforeScale;
  applyGraphScale(afterScale);
  viewport.scrollLeft = contentX * afterScale - (event.clientX - rect.left);
  viewport.scrollTop = contentY * afterScale - (event.clientY - rect.top);
}

function startPanning(event) {
  if (event.button !== 0 || event.target.closest(".graph-node")) {
    return;
  }
  elements.graphViewport.focus({ preventScroll: true });
  state.pan = {
    pointerId: event.pointerId,
    clientX: event.clientX,
    clientY: event.clientY,
    scrollLeft: elements.graphViewport.scrollLeft,
    scrollTop: elements.graphViewport.scrollTop,
  };
  elements.graphViewport.classList.add("panning");
  try {
    elements.graphViewport.setPointerCapture(event.pointerId);
  } catch {
  }
  event.preventDefault();
}

function movePanning(event) {
  if (!state.pan || event.pointerId !== state.pan.pointerId) {
    return;
  }
  elements.graphViewport.scrollLeft = state.pan.scrollLeft - (event.clientX - state.pan.clientX);
  elements.graphViewport.scrollTop = state.pan.scrollTop - (event.clientY - state.pan.clientY);
}

function stopPanning(event) {
  if (!state.pan || event.pointerId !== state.pan.pointerId) {
    return;
  }
  try {
    if (elements.graphViewport.hasPointerCapture(event.pointerId)) {
      elements.graphViewport.releasePointerCapture(event.pointerId);
    }
  } catch {
  }
  state.pan = null;
  elements.graphViewport.classList.remove("panning");
}

function zoomAroundViewportCenter(scale) {
  if (!state.currentSnapshot) {
    return;
  }
  const viewport = elements.graphViewport;
  const beforeScale = currentScale();
  const centerX = viewport.scrollLeft + viewport.clientWidth / 2;
  const centerY = viewport.scrollTop + viewport.clientHeight / 2;
  applyGraphScale(scale);
  const ratio = currentScale() / beforeScale;
  viewport.scrollLeft = centerX * ratio - viewport.clientWidth / 2;
  viewport.scrollTop = centerY * ratio - viewport.clientHeight / 2;
}

function startResizing(event) {
  if (event.button !== 0) {
    return;
  }
  state.resize = {
    pointerId: event.pointerId,
    clientY: event.clientY,
    height: elements.graphViewport.getBoundingClientRect().height,
  };
  elements.graphResizeHandle.setPointerCapture(event.pointerId);
  event.preventDefault();
}

function moveResizing(event) {
  if (!state.resize || event.pointerId !== state.resize.pointerId) {
    return;
  }
  const height = Math.min(1600, Math.max(480, state.resize.height + event.clientY - state.resize.clientY));
  elements.graphViewport.style.height = `${Math.round(height)}px`;
}

function stopResizing(event) {
  if (!state.resize || event.pointerId !== state.resize.pointerId) {
    return;
  }
  if (elements.graphResizeHandle.hasPointerCapture(event.pointerId)) {
    elements.graphResizeHandle.releasePointerCapture(event.pointerId);
  }
  state.resize = null;
}

function resizeWithKeyboard(event) {
  if (!["ArrowUp", "ArrowDown"].includes(event.key)) {
    return;
  }
  const delta = event.key === "ArrowDown" ? 40 : -40;
  const height = elements.graphViewport.getBoundingClientRect().height;
  elements.graphViewport.style.height = `${Math.min(1600, Math.max(480, height + delta))}px`;
  event.preventDefault();
}

function saveSvg() {
  if (!state.selectedTreeId) {
    return;
  }
  const link = document.createElement("a");
  link.href = `/api/trees/${encodeURIComponent(state.selectedTreeId)}/svg`;
  link.download = "";
  document.body.append(link);
  link.click();
  link.remove();
}

async function pickTree() {
  elements.pickTreeButton.disabled = true;
  try {
    const payload = await request("/api/tree-picker", { method: "POST", body: "{}" });
    if (!payload.selected) {
      setMessage("File selection canceled.");
      return;
    }
    await refreshTrees();
    selectTree(payload.tree.tree_id);
    setMessage("Tree registered.");
  } catch (error) {
    setMessage(error.message, true);
    handleRequestFailure(error);
  } finally {
    elements.pickTreeButton.disabled = false;
  }
}

async function connectClient() {
  if (state.clientId || state.connecting) {
    return;
  }
  state.connecting = true;
  setConnectionStatus("connecting");
  try {
    const payload = await request("/api/clients", { method: "POST", body: "{}" });
    state.clientId = payload.client_id;
    if (state.reconnectTimer !== null) {
      window.clearTimeout(state.reconnectTimer);
      state.reconnectTimer = null;
    }
    setConnectionStatus("connected");
    if (state.messageIsConnectionError) {
      setMessage("");
    }
    const interval = Math.max(payload.heartbeat_seconds * 500, 1000);
    const clientId = state.clientId;
    clearHeartbeat();
    state.heartbeatTimer = window.setInterval(() => {
      if (state.clientId !== clientId) {
        return;
      }
      request(`/api/clients/${encodeURIComponent(clientId)}/heartbeat`, {
        method: "POST",
        body: "{}",
      }).catch(() => {
        if (state.clientId === clientId) {
          disconnectClient();
        }
      });
    }, interval);
  } catch {
    disconnectClient();
  } finally {
    state.connecting = false;
  }
}

elements.refreshButton.addEventListener("click", () => refreshSnapshot(true));
elements.saveSvgButton.addEventListener("click", saveSvg);
elements.pickTreeButton.addEventListener("click", pickTree);
elements.sidebarToggle.addEventListener("click", () => setSidebarCollapsed(!state.sidebarCollapsed));
elements.blackboardToggle.addEventListener("click", toggleBlackboard);
elements.zoomSlider.addEventListener("input", () => zoomAroundViewportCenter(Number(elements.zoomSlider.value) / 100));
elements.graphViewport.addEventListener("wheel", zoomAroundPointer, { passive: false });
elements.graphViewport.addEventListener("pointerdown", startPanning);
elements.graphViewport.addEventListener("pointermove", movePanning);
elements.graphViewport.addEventListener("pointerup", stopPanning);
elements.graphViewport.addEventListener("pointercancel", stopPanning);
elements.graphResizeHandle.addEventListener("pointerdown", startResizing);
elements.graphResizeHandle.addEventListener("pointermove", moveResizing);
elements.graphResizeHandle.addEventListener("pointerup", stopResizing);
elements.graphResizeHandle.addEventListener("pointercancel", stopResizing);
elements.graphResizeHandle.addEventListener("keydown", resizeWithKeyboard);
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
  state.refreshTimer = window.setInterval(refreshTrees, AUTO_REFRESH_MS);
  state.blackboardTimer = window.setInterval(renderBlackboard, 60000);
});
