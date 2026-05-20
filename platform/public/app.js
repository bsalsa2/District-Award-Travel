// Main application controller for District Award Travel 3D Dashboard
import { WebGPUEngine } from './webgpu-engine.js';
import { AIEngine } from './ai-engine.js';
import { DataService } from './data-service.js';

class DistrictAwardTravelApp {
    constructor() {
        this.webgpuEngine = null;
        this.aiEngine = null;
        this.dataService = null;
        this.selectedRoute = null;
        this.animationFrameId = null;
        this.lastUpdateTime = 0;
        this.fpsCounter = 0;
        this.fpsHistory = [];
        this.maxFpsSamples = 60;

        this.init();
    }

    async init() {
        console.log('🚀 District Award Travel 3D Dashboard initializing...');

        // Initialize services
        this.dataService = new DataService();
        this.aiEngine = new AIEngine(this.dataService);
        this.webgpuEngine = new WebGPUEngine('webgl-canvas');

        // Load initial data
        await this.loadInitialData();

        // Set up event listeners
        this.setupEventListeners();

        // Start rendering loop
        this.startRendering();

        // Set up periodic updates
        this.setupPeriodicUpdates();

        console.log('✅ District Award Travel 3D Dashboard ready');
    }

    async loadInitialData() {
        try {
            console.log('📊 Loading initial data...');

            // Load flight routes
            const routes = await this.dataService.fetchFlightRoutes();
            this.webgpuEngine.setFlightRoutes(routes);

            // Load airport data
            const airports = await this.dataService.fetchAirports();
            this.webgpuEngine.setAirports(airports);

            // Load AI recommendations
            const recommendations = await this.aiEngine.generateRecommendations();
            this.updateRecommendations(recommendations);

            console.log(`✅ Loaded ${routes.length} routes, ${airports.length} airports`);
        } catch (error) {
            console.error('❌ Failed to load initial data:', error);
            // Fallback to sample data
            this.loadSampleData();
        }
    }

    loadSampleData() {
        console.log('📝 Loading sample data as fallback...');

        const sampleRoutes = [
            { id: 'route-001', from: 'JFK', to: 'LAX', distance: 2475, duration: 5.5, price: 25000, airline: 'AA', program: 'AA Advantage' },
            { id: 'route-002', from: 'LAX', to: 'HND', distance: 5476, duration: 11, price: 65000, airline: 'NH', program: 'ANA Mileage Club' },
            { id: 'route-003', from: 'LHR', to: 'JFK', distance: 3459, duration: 7.5, price: 45000, airline: 'BA', program: 'Aviator' },
            { id: 'route-004', from: 'SIN', to: 'EWR', distance: 9512, duration: 18, price: 85000, airline: 'SQ', program: 'United MileagePlus' },
        ];

        const sampleAirports = [
            { code: 'JFK', name: 'John F. Kennedy International Airport', lat: 40.6413, lon: -73.7781, country: 'USA' },
            { code: 'LAX', name: 'Los Angeles International Airport', lat: 33.9425, lon: -118.4081, country: 'USA' },
            { code: 'HND', name: 'Haneda Airport', lat: 35.5494, lon: 139.7798, country: 'Japan' },
            { code: 'LHR', name: 'Heathrow Airport', lat: 51.4700, lon: -0.4543, country: 'UK' },
            { code: 'SIN', name: 'Singapore Changi Airport', lat: 1.3592, lon: 103.9893, country: 'Singapore' },
            { code: 'EWR', name: 'Newark Liberty International Airport', lat: 40.6892, lon: -74.1745, country: 'USA' },
        ];

        this.webgpuEngine.setFlightRoutes(sampleRoutes);
        this.webgpuEngine.setAirports(sampleAirports);

        console.log('✅ Sample data loaded');
    }

    setupEventListeners() {
        // Search functionality
        document.getElementById('search-btn').addEventListener('click', () => {
            const query = document.getElementById('search-input').value.trim();
            if (query) {
                this.handleSearch(query);
            }
        });

        document.getElementById('search-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const query = e.target.value.trim();
                if (query) {
                    this.handleSearch(query);
                }
            }
        });

        // Time slider
        document.getElementById('time-slider').addEventListener('input', (e) => {
            const time = parseInt(e.target.value);
            document.getElementById('time-value').textContent = `${time}:00`;
            this.webgpuEngine.setTimeOfDay(time);
        });

        // Density slider
        document.getElementById('density-slider').addEventListener('input', (e) => {
            const density = parseInt(e.target.value);
            this.webgpuEngine.setRouteDensity(density);
        });

        // AI mode
        document.getElementById('ai-mode').addEventListener('change', (e) => {
            this.aiEngine.setFocusMode(e.target.value);
            this.updateRecommendations(this.aiEngine.getCurrentRecommendations());
        });

        // Close route details
        document.getElementById('close-details').addEventListener('click', () => {
            this.hideRouteDetails();
        });

        // Route selection
        this.webgpuEngine.onRouteSelected = (routeId) => {
            this.handleRouteSelection(routeId);
        };

        // Window resize
        window.addEventListener('resize', () => {
            this.webgpuEngine.handleResize();
        });
    }

    handleSearch(query) {
        console.log(`🔍 Searching for: ${query}`);

        // Search in routes and airports
        const results = this.dataService.search(query);

        if (results.routes.length > 0) {
            // Focus on first route
            this.handleRouteSelection(results.routes[0].id);
            this.webgpuEngine.highlightRoute(results.routes[0].id);
        } else if (results.airports.length > 0) {
            // Center on airport
            const airport = results.airports[0];
            this.webgpuEngine.centerOnAirport(airport.code);
        }

        // Update UI
        this.updateSearchResults(results);
    }

    handleRouteSelection(routeId) {
        const route = this.dataService.getRouteById(routeId);
        if (route) {
            this.selectedRoute = route;
            this.showRouteDetails(route);
            this.updateRouteList(routeId);
        }
    }

    updateRouteList(selectedId) {
        const routeList = document.getElementById('route-list');
        routeList.innerHTML = '';

        const routes = this.dataService.getAllRoutes();
        routes.forEach(route => {
            const item = document.createElement('div');
            item.className = `route-item ${route.id === selectedId ? 'active' : ''}`;
            item.textContent = `${route.from} → ${route.to} (${route.price} pts)`;
            item.addEventListener('click', () => {
                this.handleRouteSelection(route.id);
                this.webgpuEngine.highlightRoute(route.id);
            });
            routeList.appendChild(item);
        });
    }

    showRouteDetails(route) {
        const panel = document.getElementById('route-details');
        const content = document.getElementById('details-content');

        content.innerHTML = `
            <div class="route-header">
                <h4>${route.from} → ${route.to}</h4>
                <span class="route-distance">${route.distance} miles</span>
            </div>
            <div class="route-details-grid">
                <div class="detail-item">
                    <span class="detail-label">Duration:</span>
                    <span class="detail-value">${route.duration} hours</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Price:</span>
                    <span class="detail-value">${route.price.toLocaleString()} award points</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Airline:</span>
                    <span class="detail-value">${route.airline}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Program:</span>
                    <span class="detail-value">${route.program}</span>
                </div>
                <div class="detail-item">
                    <span class="detail-label">Award Ratio:</span>
                    <span class="detail-value">${(route.price / route.distance).toFixed(2)} pts/mile</span>
                </div>
            </div>
            <div class="route-actions">
                <button class="btn-primary">View Award Options</button>
                <button class="btn-secondary">Compare Routes</button>
            </div>
        `;

        panel.style.display = 'block';
    }

    hideRouteDetails() {
        document.getElementById('route-details').style.display = 'none';
        this.selectedRoute = null;
    }

    updateRecommendations(recommendations) {
        const recommendationsEl = document.getElementById('recommendations');
        recommendationsEl.innerHTML = '';

        if (recommendations.length === 0) {
            recommendationsEl.innerHTML = '<div class="recommendation-card">No recommendations available. Try adjusting your preferences.</div>';
            return;
        }

        recommendations.forEach(rec => {
            const card = document.createElement('div');
            card.className = 'recommendation-card';
            card.innerHTML = `
                <strong>${rec.title}</strong><br>
                ${rec.description}<br>
                <small>Value: ${rec.value} pts | ${rec.savings} pts saved</small>
            `;
            recommendationsEl.appendChild(card);
        });
    }

    updateSearchResults(results) {
        console.log('📊 Search results:', results);
        // Could update a search results panel if we had one
    }

    updateFPSDisplay(fps) {
        this.fpsCounter++;
        this.fpsHistory.push(fps);

        if (this.fpsHistory.length > this.maxFpsSamples) {
            this.fpsHistory.shift();
        }

        const avgFps = this.fpsHistory.reduce((a, b) => a + b, 0) / this.fpsHistory.length;
        document.getElementById('fps-counter').textContent = `${Math.round(avgFps)} FPS`;
    }

    updateLastUpdate() {
        const now = new Date();
        document.getElementById('last-update').textContent = now.toLocaleTimeString();
    }

    setupPeriodicUpdates() {
        // Update recommendations periodically
        setInterval(async () => {
            const recommendations = await this.aiEngine.generateRecommendations();
            this.updateRecommendations(recommendations);
        }, 30000); // Every 30 seconds

        // Update data freshness
        setInterval(() => {
            this.updateLastUpdate();
        }, 10000); // Every 10 seconds
    }

    startRendering() {
        const renderLoop = (timestamp) => {
            // Calculate FPS
            const now = performance.now();
            if (this.lastUpdateTime) {
                const delta = now - this.lastUpdateTime;
                const fps = 1000 / delta;
                this.updateFPSDisplay(fps);
            }
            this.lastUpdateTime = now;

            // Update engines
            if (this.webgpuEngine) {
                this.webgpuEngine.update(timestamp);
            }

            if (this.aiEngine) {
                this.aiEngine.update(timestamp);
            }

            // Continue loop
            this.animationFrameId = requestAnimationFrame(renderLoop);
        };

        this.animationFrameId = requestAnimationFrame(renderLoop);
    }

    destroy() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
        }
        if (this.webgpuEngine) {
            this.webgpuEngine.destroy();
        }
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.districtApp = new DistrictAwardTravelApp();

    // Handle page visibility changes
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            if (window.districtApp) {
                window.districtApp.destroy();
            }
        } else {
            if (window.districtApp) {
                window.districtApp.startRendering();
            }
        }
    });
});
