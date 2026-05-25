import networkx as nx
import sqlite3

class GraphDatabase:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.conn = sqlite3.connect("graph_database.db")
        self.cursor = self.conn.cursor()
        
        # Create the graph database schema if it doesn't exist
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY,
                type TEXT,
                label TEXT
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY,
                source INTEGER,
                target INTEGER,
                label TEXT,
                FOREIGN KEY (source) REFERENCES nodes (id),
                FOREIGN KEY (target) REFERENCES nodes (id)
            )
        """)
        
        self.conn.commit()
        
    def add_node(self, node_id, node_type, node_label):
        """
        Add a node to the graph database.
        
        Args:
        node_id (int): The ID of the node.
        node_type (str): The type of the node.
        node_label (str): The label of the node.
        """
        self.cursor.execute("""
            INSERT INTO nodes (id, type, label) VALUES (?, ?, ?)
        """, (node_id, node_type, node_label))
        self.conn.commit()
        
    def add_edge(self, edge_id, source_id, target_id, edge_label):
        """
        Add an edge to the graph database.
        
        Args:
        edge_id (int): The ID of the edge.
        source_id (int): The ID of the source node.
        target_id (int): The ID of the target node.
        edge_label (str): The label of the edge.
        """
        self.cursor.execute("""
            INSERT INTO edges (id, source, target, label) VALUES (?, ?, ?, ?)
        """, (edge_id, source_id, target_id, edge_label))
        self.conn.commit()
        
    def search(self, query):
        """
        Search the graph database using a natural language query.
        
        Args:
        query (str): The natural language query.
        
        Returns:
        list: A list of search results.
        """
        # Tokenize the query
        tokens = query.split()
        
        # Find nodes that match the tokens
        nodes = []
        for token in tokens:
            self.cursor.execute("""
                SELECT * FROM nodes WHERE label LIKE ?
            """, (f"%{token}%",))
            nodes.extend(self.cursor.fetchall())
        
        # Find edges that connect the nodes
        edges = []
        for node in nodes:
            self.cursor.execute("""
                SELECT * FROM edges WHERE source = ? OR target = ?
            """, (node[0], node[0]))
            edges.extend(self.cursor.fetchall())
        
        # Return the search results
        return nodes + edges

    def close(self):
        self.conn.close()
