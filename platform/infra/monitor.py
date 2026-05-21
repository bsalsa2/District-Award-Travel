import prometheus_client
from prometheus_client import Counter, Gauge, Histogram

# Create metrics
search_query_latency = Histogram('search_query_latency', 'Search query latency')
booking_success_rate = Gauge('booking_success_rate', 'Booking success rate')
system_uptime = Gauge('system_uptime', 'System uptime')

# Example usage
def search_query():
    start_time = prometheus_client.time()
    # Simulate search query
    import time
    time.sleep(1)
    end_time = prometheus_client.time()
    search_query_latency.observe(end_time - start_time)

def book_flight():
    # Simulate booking
    import random
    if random.random() < 0.9:
        booking_success_rate.set(1)
    else:
        booking_success_rate.set(0)

def main():
    # Start HTTP server
    prometheus_client.start_http_server(8000)

    while True:
        search_query()
        book_flight()
        system_uptime.set(1)
        import time
        time.sleep(1)

if __name__ == '__main__':
    main()
