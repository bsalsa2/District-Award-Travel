"""
Award Travel Recommendation Engine
Uses collaborative filtering, content-based filtering, and hybrid approaches
to suggest optimal award travel options based on user preferences and historical data.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
import logging
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AwardTravelRecommender:
    """
    Hybrid recommendation system for award travel options.
    Combines collaborative filtering, content-based filtering, and business rules.
    """

    def __init__(self, data_path: str = "data/award_travel.db"):
        self.data_path = data_path
        self.user_preferences = {}
        self.travel_data = None
        self.user_history = None
        self.airline_similarity = None
        self.destination_similarity = None
        self.model_weights = {
            'collaborative': 0.4,
            'content': 0.3,
            'business_rules': 0.3
        }
        self.load_data()

    def load_data(self):
        """Load travel data, user preferences, and historical data"""
        try:
            # Load travel options data
            self.travel_data = pd.read_csv('data/travel_options.csv')

            # Load user preferences
            if os.path.exists('data/user_preferences.json'):
                with open('data/user_preferences.json', 'r') as f:
                    self.user_preferences = json.load(f)

            # Load user history
            if os.path.exists('data/user_history.csv'):
                self.user_history = pd.read_csv('data/user_history.csv')

            # Precompute similarities
            self._precompute_similarities()

            logger.info("Successfully loaded recommendation engine data")
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise

    def _precompute_similarities(self):
        """Precompute similarity matrices for airlines and destinations"""
        try:
            # Airline similarity based on route networks
            airlines = self.travel_data['airline'].unique()
            airline_matrix = np.zeros((len(airlines), len(airlines)))

            for i, airline1 in enumerate(airlines):
                for j, airline2 in enumerate(airlines):
                    if airline1 == airline2:
                        airline_matrix[i][j] = 1.0
                    else:
                        # Simple similarity based on common destinations
                        dests1 = set(self.travel_data[self.travel_data['airline'] == airline1]['destination'])
                        dests2 = set(self.travel_data[self.travel_data['airline'] == airline2]['destination'])
                        common = len(dests1.intersection(dests2))
                        airline_matrix[i][j] = common / max(len(dests1), len(dests2), 1)

            self.airline_similarity = pd.DataFrame(
                airline_matrix,
                index=airlines,
                columns=airlines
            )

            # Destination similarity based on traveler preferences
            destinations = self.travel_data['destination'].unique()
            dest_matrix = np.zeros((len(destinations), len(destinations)))

            for i, dest1 in enumerate(destinations):
                for j, dest2 in enumerate(destinations):
                    if dest1 == dest2:
                        dest_matrix[i][j] = 1.0
                    else:
                        # Simple similarity based on common airlines
                        airlines1 = set(self.travel_data[self.travel_data['destination'] == dest1]['airline'])
                        airlines2 = set(self.travel_data[self.travel_data['destination'] == dest2]['airline'])
                        common = len(airlines1.intersection(airlines2))
                        dest_matrix[i][j] = common / max(len(airlines1), len(airlines2), 1)

            self.destination_similarity = pd.DataFrame(
                dest_matrix,
                index=destinations,
                columns=destinations
            )

        except Exception as e:
            logger.error(f"Error precomputing similarities: {e}")
            raise

    def update_user_preferences(self, user_id: str, preferences: Dict):
        """Update user preferences and save to storage"""
        self.user_preferences[user_id] = preferences
        self._save_preferences()

    def _save_preferences(self):
        """Save user preferences to JSON file"""
        try:
            with open('data/user_preferences.json', 'w') as f:
                json.dump(self.user_preferences, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving preferences: {e}")

    def get_collaborative_filtering_recommendations(self, user_id: str, n: int = 5) -> List[Dict]:
        """
        Get recommendations based on similar users' preferences
        """
        if user_id not in self.user_preferences:
            return []

        try:
            user_prefs = self.user_preferences[user_id]
            target_prefs = {
                'destinations': user_prefs.get('preferred_destinations', []),
                'airlines': user_prefs.get('preferred_airlines', []),
                'budget': user_prefs.get('budget', 5000),
                'travel_style': user_prefs.get('travel_style', 'balanced')
            }

            # Find similar users
            similar_users = []
            for uid, prefs in self.user_preferences.items():
                if uid == user_id:
                    continue

                # Simple similarity metric
                score = 0
                if 'preferred_destinations' in prefs and 'preferred_destinations' in target_prefs:
                    common_dests = set(prefs['preferred_destinations']).intersection(set(target_prefs['destinations']))
                    score += len(common_dests) * 0.3

                if 'preferred_airlines' in prefs and 'preferred_airlines' in target_prefs:
                    common_airlines = set(prefs['preferred_airlines']).intersection(set(target_prefs['airlines']))
                    score += len(common_airlines) * 0.4

                if 'budget' in prefs and 'budget' in target_prefs:
                    budget_diff = abs(prefs['budget'] - target_prefs['budget'])
                    score += max(0, 1000 - budget_diff) * 0.0003

                if score > 0:
                    similar_users.append((uid, score))

            # Sort by similarity score
            similar_users.sort(key=lambda x: x[1], reverse=True)
            similar_user_ids = [uid for uid, _ in similar_users[:10]]

            # Get travel options preferred by similar users
            recommendations = []
            for uid in similar_user_ids:
                if uid in self.user_history['user_id'].values:
                    user_history = self.user_history[self.user_history['user_id'] == uid]
                    for _, row in user_history.iterrows():
                        travel_id = row['travel_option_id']
                        travel_option = self.travel_data[self.travel_data['id'] == travel_id]
                        if not travel_option.empty:
                            recommendations.append(travel_option.iloc[0].to_dict())

            # Remove duplicates and sort by score
            unique_recs = []
            seen = set()
            for rec in recommendations:
                rec_id = rec['id']
                if rec_id not in seen:
                    seen.add(rec_id)
                    unique_recs.append(rec)

            # Score based on frequency in similar users' history
            rec_scores = {}
            for rec in unique_recs:
                rec_id = rec['id']
                count = sum(1 for uid in similar_user_ids
                          if uid in self.user_history['user_id'].values
                          and rec_id in self.user_history[self.user_history['user_id'] == uid]['travel_option_id'].values)
                rec_scores[rec_id] = count

            # Sort by score
            unique_recs.sort(key=lambda x: rec_scores.get(x['id'], 0), reverse=True)

            return unique_recs[:n]

        except Exception as e:
            logger.error(f"Error in collaborative filtering: {e}")
            return []

    def get_content_based_recommendations(self, user_id: str, n: int = 5) -> List[Dict]:
        """
        Get recommendations based on user preferences and travel option features
        """
        if user_id not in self.user_preferences:
            return []

        try:
            user_prefs = self.user_preferences[user_id]
            target_prefs = {
                'destinations': user_prefs.get('preferred_destinations', []),
                'airlines': user_prefs.get('preferred_airlines', []),
                'budget': user_prefs.get('budget', 5000),
                'travel_style': user_prefs.get('travel_style', 'balanced'),
                'season': user_prefs.get('season', 'any')
            }

            # Filter travel options based on preferences
            filtered = self.travel_data.copy()

            # Filter by destination if specified
            if target_prefs['destinations']:
                filtered = filtered[filtered['destination'].isin(target_prefs['destinations'])]

            # Filter by airline if specified
            if target_prefs['airlines']:
                filtered = filtered[filtered['airline'].isin(target_prefs['airlines'])]

            # Filter by budget
            filtered = filtered[filtered['points_required'] <= target_prefs['budget']]

            # Filter by travel style (simple mapping)
            style_mapping = {
                'luxury': ['first_class', 'business_class'],
                'adventure': ['economy', 'premium_economy'],
                'family': ['economy', 'premium_economy'],
                'balanced': ['economy', 'premium_economy', 'business_class']
            }
            if target_prefs['travel_style'] in style_mapping:
                filtered = filtered[filtered['cabin_class'].isin(style_mapping[target_prefs['travel_style']])]

            # If no results, relax filters
            if len(filtered) == 0:
                if target_prefs['destinations']:
                    filtered = self.travel_data.copy()
                if target_prefs['airlines']:
                    filtered = filtered[filtered['airline'].isin(target_prefs['airlines'])]
                filtered = filtered[filtered['points_required'] <= target_prefs['budget'] * 1.5]

            # Score based on feature matching
            scored = []
            for _, row in filtered.iterrows():
                score = 0

                # Destination match
                if target_prefs['destinations']:
                    if row['destination'] in target_prefs['destinations']:
                        score += 1.0

                # Airline match
                if target_prefs['airlines']:
                    if row['airline'] in target_prefs['airlines']:
                        score += 1.0

                # Budget match
                budget_score = 1.0 - (row['points_required'] / max(target_prefs['budget'], 1))
                score += budget_score * 0.5

                # Travel style match
                if row['cabin_class'] in style_mapping.get(target_prefs['travel_style'], []):
                    score += 0.7

                scored.append((row.to_dict(), score))

            # Sort by score
            scored.sort(key=lambda x: x[1], reverse=True)

            # Return top n
            return [item[0] for item in scored[:n]]

        except Exception as e:
            logger.error(f"Error in content-based filtering: {e}")
            return []

    def get_business_rules_recommendations(self, user_id: str, n: int = 5) -> List[Dict]:
        """
        Get recommendations based on business rules and promotions
        """
        try:
            recommendations = []

            # Get current date
            today = datetime.now()
            current_month = today.month
            current_year = today.year

            # Rule 1: Seasonal promotions (e.g., summer travel in June-August)
            if 6 <= current_month <= 8:
                summer_dests = ['Europe', 'Japan', 'Australia', 'Canada']
                summer_options = self.travel_data[self.travel_data['destination'].isin(summer_dests)]
                summer_options = summer_options.sort_values('points_required')
                recommendations.extend(summer_options.head(n).to_dict('records'))

            # Rule 2: New routes or special offers
            special_offers = self.travel_data[self.travel_data['is_special_offer'] == True]
            if not special_offers.empty:
                recommendations.extend(special_offers.head(n).to_dict('records'))

            # Rule 3: High-value redemptions (best value for points)
            if not self.travel_data.empty:
                # Calculate value score (points per dollar equivalent)
                self.travel_data['value_score'] = self.travel_data['points_required'] / (
                    self.travel_data['estimated_retail_price'] + 1
                )
                top_value = self.travel_data.sort_values('value_score').head(n)
                recommendations.extend(top_value.to_dict('records'))

            # Remove duplicates
            seen = set()
            unique_recs = []
            for rec in recommendations:
                rec_id = rec.get('id')
                if rec_id and rec_id not in seen:
                    seen.add(rec_id)
                    unique_recs.append(rec)

            return unique_recs[:n]

        except Exception as e:
            logger.error(f"Error in business rules recommendations: {e}")
            return []

    def get_hybrid_recommendations(self, user_id: str, n: int = 5) -> List[Dict]:
        """
        Get hybrid recommendations combining all approaches
        """
        try:
            # Get recommendations from each approach
            collaborative = self.get_collaborative_filtering_recommendations(user_id, n * 3)
            content = self.get_content_based_recommendations(user_id, n * 3)
            business = self.get_business_rules_recommendations(user_id, n * 3)

            # Combine and score
            all_recs = collaborative + content + business
            rec_scores = {}

            # Score each recommendation
            for rec in all_recs:
                rec_id = rec['id']
                score = 0

                # Score based on source
                if rec in collaborative:
                    score += self.model_weights['collaborative']
                if rec in content:
                    score += self.model_weights['content']
                if rec in business:
                    score += self.model_weights['business_rules']

                # Score based on recency (if available)
                if 'last_updated' in rec:
                    try:
                        update_date = datetime.strptime(rec['last_updated'], '%Y-%m-%d')
                        days_old = (datetime.now() - update_date).days
                        recency_score = max(0, 1 - (days_old / 365))  # 1 year half-life
                        score += recency_score * 0.2
                    except:
                        pass

                rec_scores[rec_id] = score

            # Sort by score
            sorted_recs = sorted(all_recs, key=lambda x: rec_scores.get(x['id'], 0), reverse=True)

            # Remove duplicates
            seen = set()
            unique_recs = []
            for rec in sorted_recs:
                rec_id = rec['id']
                if rec_id not in seen:
                    seen.add(rec_id)
                    unique_recs.append(rec)
                    if len(unique_recs) >= n:
                        break

            return unique_recs

        except Exception as e:
            logger.error(f"Error in hybrid recommendations: {e}")
            return []

    def get_recommendations(self, user_id: str, n: int = 5) -> Dict:
        """
        Main entry point for getting recommendations
        """
        try:
            recommendations = self.get_hybrid_recommendations(user_id, n)

            # Add metadata
            result = {
                'user_id': user_id,
                'generated_at': datetime.now().isoformat(),
                'recommendation_count': len(recommendations),
                'recommendations': recommendations,
                'model_weights': self.model_weights,
                'status': 'success'
            }

            return result

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return {
                'user_id': user_id,
                'generated_at': datetime.now().isoformat(),
                'recommendation_count': 0,
                'recommendations': [],
                'error': str(e),
                'status': 'error'
            }

# Example usage
if __name__ == "__main__":
    # Initialize recommender
    recommender = AwardTravelRecommender()

    # Example user preferences
    sample_prefs = {
        'preferred_destinations': ['Japan', 'Europe', 'Australia'],
        'preferred_airlines': ['ANA', 'JAL', 'Qantas'],
        'budget': 80000,
        'travel_style': 'luxury',
        'season': 'summer'
    }

    # Update user preferences
    recommender.update_user_preferences('user123', sample_prefs)

    # Get recommendations
    recommendations = recommender.get_recommendations('user123', 5)
    print(f"Generated {recommendations['recommendation_count']} recommendations")
    for rec in recommendations['recommendations']:
        print(f"- {rec['destination']} with {rec['airline']} ({rec['points_required']} points)")
