class AwardDashboard {
  constructor() {
    this.clientId = this.getClientId();
    this.apiBaseUrl = '/api/v1';
    this.metrics = {
      totalMiles: 0,
      redeemedMiles: 0,
      redemptionHistory: [],
      awardAvailability: {},
      recommendations: []
    };
    this.initEventListeners();
    this.loadInitialData();
  }

  getClientId() {
    // In a real app, this would come from authentication
    return 'client_12345';
  }

  async loadInitialData() {
    try {
      await this.fetchMetrics();
      await this.fetchRedemptionHistory();
      await this.fetchAwardAvailability();
      await this.fetchRecommendations();
      this.renderDashboard();
    } catch (error) {
      console.error('Failed to load initial data:', error);
      this.showError('Failed to load dashboard data. Please try again.');
    }
  }

  async fetchMetrics() {
    const response = await fetch(`${this.apiBaseUrl}/clients/${this.clientId}/metrics`);
    if (!response.ok) throw new Error('Failed to fetch metrics');
    const data = await response.json();
    this.metrics.totalMiles = data.total_award_miles;
    this.metrics.redeemedMiles = data.redeemed_miles_this_year;
  }

  async fetchRedemptionHistory() {
    const response = await fetch(`${this.apiBaseUrl}/clients/${this.clientId}/redemptions/history`);
    if (!response.ok) throw new Error('Failed to fetch redemption history');
    this.metrics.redemptionHistory = await response.json();
  }

  async fetchAwardAvailability() {
    const response = await fetch(`${this.apiBaseUrl}/clients/${this.clientId}/awards/availability`);
    if (!response.ok) throw new Error('Failed to fetch award availability');
    this.metrics.awardAvailability = await response.json();
  }

  async fetchRecommendations() {
    const response = await fetch(`${this.apiBaseUrl}/clients/${this.clientId}/recommendations`);
    if (!response.ok) throw new Error('Failed to fetch recommendations');
    this.metrics.recommendations = await response.json();
    this.calculateBestValue();
  }

  calculateBestValue() {
    if (this.metrics.recommendations.length === 0) return;

    let bestRatio = 0;
    let bestRoute = '';

    this.metrics.recommendations.forEach(rec => {
      const ratio = rec.miles_required / rec.cash_cost;
      if (ratio > bestRatio) {
        bestRatio = ratio;
        bestRoute = `${rec.departure_airport}-${rec.arrival_airport}`;
      }
    });

    document.getElementById('best-value').textContent =
      bestRatio > 0 ? `${bestRatio.toFixed(2)}x` : 'N/A';
  }

  renderDashboard() {
    this.updateSummaryCards();
    this.renderRedemptionChart();
    this.renderAvailabilityDonut();
    this.renderRecommendationsTable();
  }

  updateSummaryCards() {
    document.getElementById('total-miles').textContent = this.metrics.totalMiles.toLocaleString();
    document.getElementById('redeemed-miles').textContent = this.metrics.redeemedMiles.toLocaleString();
  }

  renderRedemptionChart() {
    const margin = { top: 20, right: 20, bottom: 30, left: 50 };
    const width = 600 - margin.left - margin.right;
    const height = 300 - margin.top - margin.bottom;

    // Clear previous chart
    d3.select('#redemption-chart').html('');

    const svg = d3.select('#redemption-chart')
      .append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${margin.left},${margin.top})`);

    // Create scales
    const x = d3.scaleBand()
      .domain(this.metrics.redemptionHistory.map(d => d.month))
      .range([0, width])
      .padding(0.1);

    const y = d3.scaleLinear()
      .domain([0, d3.max(this.metrics.redemptionHistory, d => d.miles_redeemed)])
      .range([height, 0]);

    // Add axes
    svg.append('g')
      .attr('class', 'x-axis')
      .attr('transform', `translate(0,${height})`)
      .call(d3.axisBottom(x));

    svg.append('g')
      .attr('class', 'y-axis')
      .call(d3.axisLeft(y));

    // Add bars
    svg.selectAll('.bar')
      .data(this.metrics.redemptionHistory)
      .enter()
      .append('rect')
      .attr('class', 'bar')
      .attr('x', d => x(d.month))
      .attr('y', d => y(d.miles_redeemed))
      .attr('width', x.bandwidth())
      .attr('height', d => height - y(d.miles_redeemed))
      .attr('fill', '#007bff')
      .on('mouseover', function() {
        d3.select(this).attr('fill', '#0056b3');
      })
      .on('mouseout', function() {
        d3.select(this).attr('fill', '#007bff');
      });

    // Add title
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', -10)
      .attr('text-anchor', 'middle')
      .style('font-size', '14px')
      .text('Miles Redeemed by Month');
  }

  renderAvailabilityDonut() {
    const margin = { top: 20, right: 20, bottom: 20, left: 20 };
    const width = 250 - margin.left - margin.right;
    const height = 250 - margin.top - margin.bottom;
    const radius = Math.min(width, height) / 2;

    // Clear previous chart
    d3.select('#availability-donut').html('');

    const svg = d3.select('#availability-donut')
      .append('svg')
      .attr('width', width + margin.left + margin.right)
      .attr('height', height + margin.top + margin.bottom)
      .append('g')
      .attr('transform', `translate(${width / 2 + margin.left},${height / 2 + margin.top})`);

    // Prepare data
    const data = Object.entries(this.metrics.awardAvailability).map(([key, value]) => ({
      label: key,
      value: value
    }));

    const color = d3.scaleOrdinal()
      .domain(data.map(d => d.label))
      .range(d3.quantize(t => d3.interpolateSpectral(t * 0.8 + 0.1), data.length).reverse());

    const pie = d3.pie()
      .value(d => d.value)
      .sort(null);

    const arc = d3.arc()
      .innerRadius(0)
      .outerRadius(radius);

    const arcs = svg.selectAll('.arc')
      .data(pie(data))
      .enter()
      .append('g')
      .attr('class', 'arc');

    arcs.append('path')
      .attr('d', arc)
      .attr('fill', d => color(d.data.label))
      .attr('stroke', 'white')
      .style('stroke-width', '2px');

    // Add labels
    arcs.append('text')
      .attr('transform', d => `translate(${arc.centroid(d)})`)
      .attr('text-anchor', 'middle')
      .text(d => d.data.value > 0 ? d.data.value : '')
      .style('font-size', '12px')
      .style('font-weight', 'bold');

    // Add legend
    const legend = svg.selectAll('.legend')
      .data(data)
      .enter()
      .append('g')
      .attr('class', 'legend')
      .attr('transform', (d, i) => `translate(${radius + 20},${i * 20 - radius})`);

    legend.append('rect')
      .attr('width', 12)
      .attr('height', 12)
      .attr('fill', d => color(d.label));

    legend.append('text')
      .attr('x', 15)
      .attr('y', 9)
      .attr('dy', '.35em')
      .text(d => d.label)
      .style('font-size', '12px')
      .attr('text-anchor', 'start');
  }

  renderRecommendationsTable() {
    const tbody = document.getElementById('recommendations-body');
    tbody.innerHTML = '';

    this.metrics.recommendations.forEach(rec => {
      const row = document.createElement('tr');

      row.innerHTML = `
        <td>${rec.departure_airport} → ${rec.arrival_airport}</td>
        <td>${rec.airline}</td>
        <td>${rec.miles_required.toLocaleString()}</td>
        <td>$${rec.cash_cost.toFixed(2)}</td>
        <td>${(rec.miles_required / rec.cash_cost).toFixed(2)}x</td>
        <td>
          <button class="btn btn-sm btn-outline-primary view-details" data-id="${rec.id}">
            <i data-feather="eye"></i> View
          </button>
        </td>
      `;

      tbody.appendChild(row);
    });

    feather.replace();
  }

  initEventListeners() {
    // Navigation
    document.getElementById('dashboard-link').addEventListener('click', (e) => {
      e.preventDefault();
      this.showSection('dashboard');
    });

    document.getElementById('analytics-link').addEventListener('click', (e) => {
      e.preventDefault();
      this.showSection('analytics');
    });

    document.getElementById('recommendations-link').addEventListener('click', (e) => {
      e.preventDefault();
      this.showSection('recommendations');
    });

    document.getElementById('settings-link').addEventListener('click', (e) => {
      e.preventDefault();
      this.showSection('settings');
    });

    // Data refresh
    document.getElementById('refresh-data').addEventListener('click', () => {
      this.refreshData();
    });

    // Export CSV
    document.getElementById('export-csv').addEventListener('click', () => {
      this.exportToCSV();
    });

    // View details for recommendations
    document.addEventListener('click', (e) => {
      if (e.target.classList.contains('view-details')) {
        const id = e.target.getAttribute('data-id');
        this.viewRecommendationDetails(id);
      }
    });
  }

  showSection(section) {
    // In a real app, this would show/hide sections
    console.log(`Showing section: ${section}`);
  }

  async refreshData() {
    try {
      await this.loadInitialData();
      this.showToast('Data refreshed successfully!');
    } catch (error) {
      console.error('Failed to refresh data:', error);
      this.showError('Failed to refresh data. Please try again.');
    }
  }

  exportToCSV() {
    // Create CSV data
    const csvData = [
      ['Route', 'Airline', 'Miles Required', 'Cash Cost', 'Value Ratio'],
      ...this.metrics.recommendations.map(rec =>
        [`${rec.departure_airport}→${rec.arrival_airport}`, rec.airline,
         rec.miles_required, rec.cash_cost, (rec.miles_required / rec.cash_cost).toFixed(2)])
    ].map(row => row.join(',')).join('\n');

    // Create download link
    const blob = new Blob([csvData], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `award-recommendations-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);

    this.showToast('Data exported to CSV!');
  }

  viewRecommendationDetails(id) {
    const rec = this.metrics.recommendations.find(r => r.id === id);
    if (rec) {
      alert(`Details for ${rec.departure_airport}→${rec.arrival_airport}\n\n` +
            `Airline: ${rec.airline}\n` +
            `Miles: ${rec.miles_required.toLocaleString()}\n` +
            `Cash: $${rec.cash_cost.toFixed(2)}\n` +
            `Ratio: ${(rec.miles_required / rec.cash_cost).toFixed(2)}x\n` +
            `Departure: ${rec.departure_date}\n` +
            `Return: ${rec.return_date}`);
    }
  }

  showToast(message) {
    // Simple toast implementation
    const toast = document.createElement('div');
    toast.className = 'toast show';
    toast.style.position = 'fixed';
    toast.style.bottom = '20px';
    toast.style.right = '20px';
    toast.style.padding = '15px';
    toast.style.backgroundColor = '#28a745';
    toast.style.color = 'white';
    toast.style.borderRadius = '5px';
    toast.style.boxShadow = '0 0.5rem 1rem rgba(0, 0, 0, 0.15)';
    toast.style.zIndex = '1050';
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => {
      toast.remove();
    }, 3000);
  }

  showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'alert alert-danger';
    errorDiv.style.marginTop = '20px';
    errorDiv.textContent = message;

    const main = document.querySelector('main');
    main.prepend(errorDiv);

    setTimeout(() => {
      errorDiv.remove();
    }, 5000);
  }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  new AwardDashboard();
});
