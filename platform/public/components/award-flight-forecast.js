import { fetch } from 'whatwg-fetch';
import { html, render } from 'lit-html';

class AwardFlightForecast extends HTMLElement {
  constructor() {
    super();
    this.forecastData = {};
  }

  connectedCallback() {
    this.fetchForecastData();
    this.render();
  }

  async fetchForecastData() {
    try {
      const response = await fetch('/api/award-flight-forecast');
      const data = await response.json();
      this.forecastData = data;
      this.render();
    } catch (error) {
      console.error(error);
    }
  }

  render() {
    const template = html`
      <h1>Award Flight Forecast</h1>
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th>Award Flight Availability</th>
          </tr>
        </thead>
        <tbody>
          ${Object.keys(this.forecastData).map(date => html`
            <tr>
              <td>${date}</td>
              <td>${this.forecastData[date]}</td>
            </tr>
          `)}
        </tbody>
      </table>
    `;
    render(template, this);
  }
}

customElements.define('award-flight-forecast', AwardFlightForecast);
