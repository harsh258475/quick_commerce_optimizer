let problemData = null;
let latestSolution = null;
let currentDataTable = "orders";

const riderColors = ["#e4572e", "#176b87", "#16a06d", "#8f4eb8", "#c48a12", "#008a91"];

function showToast(message, type = "info") {
    const toast = document.getElementById("toast");
    toast.textContent = message;
    toast.className = `toast show ${type}`;
    setTimeout(() => toast.classList.remove("show"), 4500);
}

function setStatus(message) {
    document.getElementById("statusText").textContent = message;
}

async function loadProblemData() {
    const response = await fetch("/api/problem-data");
    const data = await response.json();
    if (!data.success) {
        throw new Error(data.detail || data.error || "Could not load problem data.");
    }
    problemData = data;
    renderSelectedOrders();
    showDataTable(currentDataTable);
    drawMap({
        nodes: [{ id: 0, type: "depot", x: 0, y: 0 }].concat(data.orders.slice(0, getOrderCount()).map(orderNode)),
        edges: [],
        routes: []
    });
}

function getOrderCount() {
    return Number.parseInt(document.getElementById("orderCount").value, 10);
}

function orderNode(order) {
    return {
        id: order.id,
        type: order.is_premium ? "premium" : "order",
        x: order.x,
        y: order.y,
        ready_min: order.ready_min,
        due_min: order.due_min
    };
}

async function solveProblem() {
    const solveBtn = document.getElementById("solveBtn");
    solveBtn.disabled = true;
    solveBtn.textContent = "Solving...";
    setStatus("Solving");

    try {
        const payload = {
            n_orders: getOrderCount(),
            n_riders: Number.parseInt(document.getElementById("riderCount").value, 10),
            service_min: Number.parseFloat(document.getElementById("serviceMin").value),
            allow_late: document.getElementById("allowLate").checked,
            late_penalty: Number.parseFloat(document.getElementById("latePenalty").value)
        };

        const response = await fetch("/api/solve-mtsp-tw", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.detail || data.error || "Solver failed.");
        }

        latestSolution = data;
        updateMetrics(data);
        renderRoutes(data.routes);
        renderSelectedOrders(data);
        drawMap(data);
        setStatus(
            data.status === "optimal"
                ? "Optimal"
                : data.status === "on_time_subset"
                    ? "On-time subset"
                    : data.status === "heuristic_fallback"
                        ? "Heuristic"
                        : "Feasible"
        );
        showToast("Routes solved successfully.", "success");
    } catch (error) {
        setStatus("Needs attention");
        showToast(error.message, "error");
    } finally {
        solveBtn.disabled = false;
        solveBtn.textContent = "Optimize Routes";
    }
}

function updateMetrics(data) {
    document.getElementById("objectiveMetric").textContent = formatRupees(data.objective);
    document.getElementById("travelMetric").textContent = formatMinutes(data.travel_minutes);
    document.getElementById("kmMetric").textContent = formatKm(data.travel_km || 0);
    document.getElementById("lateMetric").textContent = formatMinutes(data.late_minutes);
    const skipped = (data.skipped_orders || []).length;
    document.getElementById("riderMetric").textContent = skipped > 0
        ? `${data.used_riders} riders, ${skipped} skipped`
        : `${data.used_riders} / ${document.getElementById("riderCount").value}`;
}

function renderRoutes(routes) {
    const routeList = document.getElementById("routeList");
    const usedRoutes = routes.filter(route => route.used);
    const skippedOrders = latestSolution?.skipped_orders || [];

    if (usedRoutes.length === 0 && skippedOrders.length === 0) {
        routeList.innerHTML = '<p class="empty">No riders were used.</p>';
        return;
    }

    const skippedHtml = skippedOrders.length === 0 ? "" : `
        <article class="route-card skipped-card">
            <div class="route-card-head">
                <h3>Skipped Orders</h3>
                <span>No late delivery allowed</span>
            </div>
            <ol>
                ${skippedOrders.map(order => `
                    <li>
                        <strong>Order ${order.order_id}</strong>
                        <span>direct travel ${formatMinutes(order.direct_minutes)} | window closes ${formatMinutes(order.due_min)}</span>
                    </li>
                `).join("")}
            </ol>
        </article>
    `;

    routeList.innerHTML = usedRoutes.map((route, index) => {
        const stops = route.stops.map(stop => `
            <li>
                <strong>Order ${stop.order_id}</strong>
                <span>arrival ${formatMinutes(stop.arrival_min)} | window ${formatMinutes(stop.ready_min)} - ${formatMinutes(stop.due_min)}</span>
                ${stop.late_min > 0 ? `<em>${formatMinutes(stop.late_min)} late</em>` : ""}
            </li>
        `).join("");

        return `
            <article class="route-card" style="border-left-color: ${riderColors[index % riderColors.length]}">
                <div class="route-card-head">
                    <h3>Rider ${route.rider_id}</h3>
                    <span>${route.path.join(" -> ")}</span>
                </div>
                <div class="route-stats">
                    <span>Load ${route.load}/${route.capacity}</span>
                    <span>${formatMinutes(route.distance)}</span>
                    <span>${formatKm(route.distance_km || 0)}</span>
                    <span>${formatMinutes(route.late_minutes)} late</span>
                </div>
                <ol>${stops}</ol>
            </article>
        `;
    }).join("") + skippedHtml;
}

function renderSelectedOrders(solution = null) {
    if (!problemData) {
        return;
    }

    const arrivals = {};
    if (solution) {
        for (const route of solution.routes) {
            for (const stop of route.stops) {
                arrivals[stop.order_id] = stop;
            }
        }
    }

    const rows = problemData.orders.slice(0, getOrderCount()).map(order => {
        const stop = arrivals[order.id];
        return `
            <tr>
                <td>${order.id}</td>
                <td>${formatMinutes(order.ready_min)}</td>
                <td>${formatMinutes(order.due_min)}</td>
                <td>${order.demand}</td>
                <td>${order.is_premium ? "Yes" : "No"}</td>
                <td>${formatRupees(order.basket_value)}</td>
                <td>${formatRupees(order.revenue)}</td>
                <td>${stop ? formatMinutes(stop.arrival_min) : "-"}</td>
                <td>${stop && stop.late_min > 0 ? formatMinutes(stop.late_min) : formatMinutes(0)}</td>
            </tr>
        `;
    }).join("");

    document.getElementById("orderTable").innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>Order</th>
                    <th>Ready</th>
                    <th>Due</th>
                    <th>Demand</th>
                    <th>Premium</th>
                    <th>Basket</th>
                    <th>Revenue</th>
                    <th>Arrival</th>
                    <th>Late</th>
                </tr>
            </thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

function showDataTable(type) {
    if (!problemData) {
        return;
    }

    currentDataTable = type;
    document.querySelectorAll(".tab-btn").forEach(button => {
        button.classList.toggle("active", button.textContent.toLowerCase().replace(" times", "") === type);
    });

    if (type === "orders") {
        renderDataTable(`
            <table>
                <thead>
                    <tr>
                        <th>Order</th>
                        <th>X km</th>
                        <th>Y km</th>
                        <th>Demand</th>
                        <th>Ready</th>
                        <th>Due</th>
                        <th>Basket</th>
                        <th>Revenue</th>
                        <th>Premium</th>
                    </tr>
                </thead>
                <tbody>
                    ${problemData.orders.map(order => `
                        <tr>
                            <td>${order.id}</td>
                            <td>${order.x.toFixed(2)} km</td>
                            <td>${order.y.toFixed(2)} km</td>
                            <td>${order.demand}</td>
                            <td>${formatMinutes(order.ready_min)}</td>
                            <td>${formatMinutes(order.due_min)}</td>
                            <td>${formatRupees(order.basket_value)}</td>
                            <td>${formatRupees(order.revenue)}</td>
                            <td>${order.is_premium ? "Yes" : "No"}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `);
        return;
    }

    if (type === "riders") {
        renderDataTable(`
            <table>
                <thead>
                    <tr>
                        <th>Rider</th>
                        <th>Capacity</th>
                        <th>Start X</th>
                        <th>Start Y</th>
                        <th>Shift start</th>
                        <th>Shift end</th>
                    </tr>
                </thead>
                <tbody>
                    ${problemData.riders.map(rider => `
                        <tr>
                            <td>${rider.id}</td>
                            <td>${rider.capacity} orders</td>
                            <td>${rider.start_x.toFixed(2)} km</td>
                            <td>${rider.start_y.toFixed(2)} km</td>
                            <td>${formatMinutes(rider.shift_start_min)}</td>
                            <td>${formatMinutes(rider.shift_end_min)}</td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `);
        return;
    }

    const travel = problemData.travel_time_matrix;
    const activeNodes = [0].concat(problemData.orders.slice(0, getOrderCount()).map(order => order.id));
    const activeSet = new Set(activeNodes);
    const visibleIndexes = travel.nodes
        .map((node, index) => ({ node, index }))
        .filter(item => activeSet.has(item.node));

    renderDataTable(`
        <p class="section-note">Travel time matrix for the selected ${activeNodes.length} nodes. Values are in minutes.</p>
        <table class="matrix-data-table">
            <thead>
                <tr>
                    <th>From / To</th>
                    ${visibleIndexes.map(item => `<th>${item.node}</th>`).join("")}
                </tr>
            </thead>
            <tbody>
                ${visibleIndexes.map(rowItem => `
                    <tr>
                        <th>${rowItem.node}</th>
                        ${visibleIndexes.map(colItem => {
                            const value = travel.matrix[rowItem.index][colItem.index];
                            return `<td>${value === null || value === undefined ? "-" : Number(value).toFixed(1)}</td>`;
                        }).join("")}
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `);
}

function renderDataTable(html) {
    document.getElementById("dataTable").innerHTML = html;
}

function drawMap(data) {
    const svg = document.getElementById("routeSvg");
    svg.innerHTML = "";

    const width = svg.clientWidth || 760;
    const height = svg.clientHeight || 560;
    const padding = 46;
    const nodes = data.nodes || [];

    if (nodes.length === 0) {
        return;
    }

    const xs = nodes.map(node => node.x);
    const ys = nodes.map(node => node.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const scaleX = value => padding + ((value - minX) / Math.max(1, maxX - minX)) * (width - padding * 2);
    const scaleY = value => height - padding - ((value - minY) / Math.max(1, maxY - minY)) * (height - padding * 2);
    const byId = Object.fromEntries(nodes.map(node => [node.id, node]));

    const defs = makeSvg("defs");
    riderColors.forEach((color, index) => {
        const marker = makeSvg("marker", {
            id: `arrow-${index}`,
            markerWidth: 10,
            markerHeight: 10,
            refX: 8,
            refY: 3,
            orient: "auto"
        });
        marker.appendChild(makeSvg("polygon", { points: "0 0, 10 3, 0 6", fill: color }));
        defs.appendChild(marker);
    });
    svg.appendChild(defs);

    const edgeLayer = makeSvg("g");
    (data.edges || []).forEach(edge => {
        const source = byId[edge.source];
        const target = byId[edge.target];
        if (!source || !target) {
            return;
        }
        const colorIndex = (edge.rider_id - 1) % riderColors.length;
        edgeLayer.appendChild(makeSvg("line", {
            x1: scaleX(source.x),
            y1: scaleY(source.y),
            x2: scaleX(target.x),
            y2: scaleY(target.y),
            stroke: riderColors[colorIndex],
            "stroke-width": 3,
            "marker-end": `url(#arrow-${colorIndex})`,
            opacity: 0.88
        }));
    });
    svg.appendChild(edgeLayer);

    const nodeLayer = makeSvg("g");
    nodes.forEach(node => {
        const cx = scaleX(node.x);
        const cy = scaleY(node.y);
        const isDepot = node.type === "depot";
        const isPremium = node.type === "premium";
        nodeLayer.appendChild(makeSvg("circle", {
            cx,
            cy,
            r: isDepot ? 18 : 13,
            fill: isDepot ? "#111827" : isPremium ? "#d64f2f" : "#f8fafc",
            stroke: isDepot ? "#111827" : "#334155",
            "stroke-width": 2
        }));
        const text = makeSvg("text", {
            x: cx,
            y: cy + 4,
            "text-anchor": "middle",
            "font-size": isDepot ? 12 : 10,
            "font-weight": 700,
            fill: isDepot || isPremium ? "#ffffff" : "#111827"
        });
        text.textContent = node.id;
        nodeLayer.appendChild(text);
    });
    svg.appendChild(nodeLayer);
}

function makeSvg(tag, attrs = {}) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
}

function formatMinutes(value) {
    return `${Number(value).toFixed(1)} minutes`;
}

function formatKm(value) {
    return `${Number(value).toFixed(2)} km`;
}

function formatRupees(value) {
    return `Rs ${Number(value).toFixed(2)}`;
}

document.addEventListener("DOMContentLoaded", async () => {
    try {
        await loadProblemData();
        document.getElementById("orderCount").addEventListener("change", () => {
            renderSelectedOrders(latestSolution);
            if (currentDataTable === "travel") {
                showDataTable("travel");
            }
            if (!latestSolution) {
                drawMap({
                    nodes: [{ id: 0, type: "depot", x: 0, y: 0 }].concat(problemData.orders.slice(0, getOrderCount()).map(orderNode)),
                    edges: []
                });
            }
        });
    } catch (error) {
        showToast(error.message, "error");
    }
});
