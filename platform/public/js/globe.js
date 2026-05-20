class AwardGlobe {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0a0a0a);
        this.camera = new THREE.PerspectiveCamera(75, this.container.clientWidth / this.container.clientHeight, 0.1, 1000);
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.container.appendChild(this.renderer.domElement);

        // Add lights
        this.addLights();

        // Create globe
        this.globe = this.createGlobe();
        this.scene.add(this.globe);

        // Add flight paths
        this.flightPaths = [];
        this.selectedRoute = null;

        // Controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.25;
        this.controls.rotateSpeed = 0.35;

        // Camera position
        this.camera.position.z = 2.5;

        // Animation loop
        this.animate();

        // Handle window resize
        window.addEventListener('resize', this.onWindowResize.bind(this));

        // Raycaster for click detection
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.container.addEventListener('click', this.onGlobeClick.bind(this), false);
    }

    addLights() {
        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xffffff, 1);
        directionalLight.position.set(1, 1, 1);
        this.scene.add(directionalLight);

        const hemisphereLight = new THREE.HemisphereLight(0xffffbb, 0x080820, 0.6);
        this.scene.add(hemisphereLight);
    }

    createGlobe() {
        const geometry = new THREE.SphereGeometry(1, 64, 64);

        // Earth texture
        const textureLoader = new THREE.TextureLoader();
        const earthTexture = textureLoader.load('assets/earth_day.jpg');
        const bumpMap = textureLoader.load('assets/earth_bump.jpg');
        const specularMap = textureLoader.load('assets/earth_specular.jpg');

        const material = new THREE.MeshPhongMaterial({
            map: earthTexture,
            bumpMap: bumpMap,
            bumpScale: 0.05,
            specularMap: specularMap,
            specular: new THREE.Color('grey'),
            shininess: 5
        });

        const globe = new THREE.Mesh(geometry, material);
        globe.rotation.y = -Math.PI / 2; // Align with prime meridian

        // Add clouds
        const cloudsGeometry = new THREE.SphereGeometry(1.01, 64, 64);
        const cloudsMaterial = new THREE.MeshPhongMaterial({
            map: textureLoader.load('assets/earth_clouds.png'),
            transparent: true,
            opacity: 0.4
        });
        const clouds = new THREE.Mesh(cloudsGeometry, cloudsMaterial);
        globe.add(clouds);

        // Add cities as points
        this.addCities(globe);

        return globe;
    }

    addCities(globe) {
        const cities = [
            { name: 'JFK', lat: 40.6413, lon: -73.7781, color: 0xff0000 },
            { name: 'LAX', lat: 33.9425, lon: -118.4081, color: 0x00ff00 },
            { name: 'LHR', lat: 51.4700, lon: -0.4543, color: 0x0000ff },
            { name: 'NRT', lat: 35.7650, lon: 140.3850, color: 0xffff00 },
            { name: 'HND', lat: 35.5494, lon: 139.7798, color: 0xff00ff },
            { name: 'CDG', lat: 49.0097, lon: 2.5479, color: 0x00ffff },
            { name: 'DXB', lat: 25.2532, lon: 55.3657, color: 0xffa500 },
            { name: 'SIN', lat: 1.3521, lon: 103.8198, color: 0x800080 }
        ];

        const geometry = new THREE.SphereGeometry(0.005, 16, 16);
        const material = new THREE.MeshBasicMaterial({ color: 0xffffff });

        cities.forEach(city => {
            const phi = (90 - city.lat) * (Math.PI / 180);
            const theta = (city.lon + 180) * (Math.PI / 180);

            const x = Math.sin(phi) * Math.cos(theta);
            const y = Math.cos(phi);
            const z = Math.sin(phi) * Math.sin(theta);

            const cityMesh = new THREE.Mesh(geometry, material.clone());
            cityMesh.position.set(x, y, z);
            cityMesh.userData = { name: city.name, type: 'city' };
            globe.add(cityMesh);

            // Add label
            this.addLabel(city.name, x, y, z);
        });
    }

    addLabel(text, x, y, z) {
        const canvas = document.createElement('canvas');
        const context = canvas.getContext('2d');
        const fontSize = 48;
        context.font = `${fontSize}px Arial`;
        context.fillStyle = 'white';
        context.fillText(text, 0, fontSize);

        const texture = new THREE.CanvasTexture(canvas);
        const material = new THREE.SpriteMaterial({ map: texture });
        const sprite = new THREE.Sprite(material);
        sprite.position.set(x * 1.1, y * 1.1, z * 1.1);
        sprite.scale.set(0.2, 0.1, 1);
        this.scene.add(sprite);
    }

    addFlightPath(departure, destination, color = 0x3498db, width = 3) {
        // Convert lat/lon to 3D coordinates
        const departurePos = this.latLonToPosition(departure.lat, departure.lon);
        const destinationPos = this.latLonToPosition(destination.lat, destination.lon);

        // Create curve
        const curve = new THREE.QuadraticBezierCurve3(
            new THREE.Vector3(departurePos.x, departurePos.y, departurePos.z),
            new THREE.Vector3(
                (departurePos.x + destinationPos.x) / 2,
                Math.max(departurePos.y, destinationPos.y) + 0.5,
                (departurePos.z + destinationPos.z) / 2
            ),
            new THREE.Vector3(destinationPos.x, destinationPos.y, destinationPos.z)
        );

        // Create tube geometry
        const tubeGeometry = new THREE.TubeGeometry(curve, 100, width * 0.001, 8, false);
        const material = new THREE.MeshBasicMaterial({
            color: new THREE.Color(color),
            transparent: true,
            opacity: 0.8
        });
        const tube = new THREE.Mesh(tubeGeometry, material);

        this.scene.add(tube);
        this.flightPaths.push({
            mesh: tube,
            departure: departure,
            destination: destination,
            curve: curve
        });

        return tube;
    }

    latLonToPosition(lat, lon) {
        const phi = (90 - lat) * (Math.PI / 180);
        const theta = (lon + 180) * (Math.PI / 180);

        return {
            x: Math.sin(phi) * Math.cos(theta),
            y: Math.cos(phi),
            z: Math.sin(phi) * Math.sin(theta)
        };
    }

    updateFlightPaths(routes) {
        // Clear existing paths
        this.flightPaths.forEach(path => this.scene.remove(path.mesh));
        this.flightPaths = [];

        // Add new paths
        routes.forEach(route => {
            const color = route.points_cost < 50000 ? 0x2ecc71 :  // Green for cheap
                         route.points_cost < 100000 ? 0xf39c12 : // Orange for medium
                         0xe74c3c; // Red for expensive

            this.addFlightPath(route.departure, route.destination, color, 2);
        });
    }

    onGlobeClick(event) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

        this.raycaster.setFromCamera(this.mouse, this.camera);

        // Check for intersection with cities
        const intersects = this.raycaster.intersectObjects(this.globe.children);

        if (intersects.length > 0) {
            const object = intersects[0].object;
            if (object.userData.type === 'city') {
                this.handleCityClick(object.userData.name);
            }
        }
    }

    handleCityClick(cityName) {
        // Dispatch custom event
        const event = new CustomEvent('citySelected', { detail: { city: cityName } });
        document.dispatchEvent(event);
    }

    onWindowResize() {
        this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    }

    animate() {
        requestAnimationFrame(this.animate.bind(this));

        // Rotate clouds
        this.globe.children.forEach(child => {
            if (child.material && child.material.map && child.material.map.image) {
                if (child.material.map.image.src.includes('clouds')) {
                    child.rotation.y += 0.0005;
                }
            }
        });

        this.controls.update();
        this.renderer.render(this.scene, this.camera);
    }

    updateAwardOptions(options) {
        // Clear previous options
        const listElement = document.getElementById('award-options-list');
        listElement.innerHTML = '';

        // Add new options
        options.forEach((option, index) => {
            const optionElement = document.createElement('div');
            optionElement.className = 'award-option';
            optionElement.innerHTML = `
                <strong>${option.airline}</strong> ${option.flight_number}<br>
                ${option.departure.city} → ${option.destination.city}<br>
                ${option.departure.date} ${option.departure.time} → ${option.destination.date} ${option.destination.time}<br>
                <small>${option.points} pts | ${option.cabin} | ${option.duration}</small>
                <button class="select-option" data-index="${index}">Select</button>
            `;
            listElement.appendChild(optionElement);
        });

        // Add event listeners to select buttons
        document.querySelectorAll('.select-option').forEach(button => {
            button.addEventListener('click', (e) => {
                const index = parseInt(e.target.getAttribute('data-index'));
                const event = new CustomEvent('awardOptionSelected', { detail: { index: index } });
                document.dispatchEvent(event);
            });
        });
    }

    updateAISuggestions(suggestions) {
        const suggestionsElement = document.getElementById('ai-suggestions');
        suggestionsElement.innerHTML = '';

        suggestions.forEach(suggestion => {
            const suggestionElement = document.createElement('div');
            suggestionElement.className = 'ai-suggestion';
            suggestionElement.innerHTML = `
                <strong>${suggestion.type}</strong>: ${suggestion.message}<br>
                <small>Potential savings: ${suggestion.savings}</small>
            `;
            suggestionsElement.appendChild(suggestionElement);
        });
    }

    updateCollaborators(collaborators) {
        const collaboratorsElement = document.getElementById('collaborators-list');
        collaboratorsElement.innerHTML = '';

        collaborators.forEach(collaborator => {
            const collaboratorElement = document.createElement('div');
            collaboratorElement.className = 'collaborator-item';
            collaboratorElement.innerHTML = `
                ${collaborator.name} (${collaborator.email})
                <button class="remove-btn" data-email="${collaborator.email}">Remove</button>
            `;
            collaboratorsElement.appendChild(collaboratorElement);
        });

        // Add event listeners to remove buttons
        document.querySelectorAll('.remove-btn').forEach(button => {
            button.addEventListener('click', (e) => {
                const email = e.target.getAttribute('data-email');
                const event = new CustomEvent('removeCollaborator', { detail: { email: email } });
                document.dispatchEvent(event);
            });
        });
    }
}

// Initialize globe when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.awardGlobe = new AwardGlobe('globe-container');
});
