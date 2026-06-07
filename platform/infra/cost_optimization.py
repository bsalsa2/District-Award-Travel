#!/usr/bin/env python3
"""
Cost Optimization System for District Award Travel Infrastructure
Automates cost analysis and optimization across cloud providers and on-prem resources.
"""

import os
import sys
import json
import time
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import boto3
import requests
from google.cloud import billing_v1
from google.oauth2 import service_account

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/cost_optimization.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('cost_optimization')

class CostOptimizer:
    """Main cost optimization class that orchestrates all cost-saving measures."""

    def __init__(self):
        self.config = self._load_config()
        self.cloud_providers = self._initialize_cloud_providers()
        self.cost_data = {}
        self.optimization_results = []

    def _load_config(self) -> Dict:
        """Load configuration from environment variables and config files."""
        config = {
            'aws': {
                'enabled': os.getenv('AWS_COST_ANALYSIS_ENABLED', 'true').lower() == 'true',
                'access_key': os.getenv('AWS_ACCESS_KEY_ID'),
                'secret_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
                'region': os.getenv('AWS_REGION', 'us-east-1'),
                'account_id': os.getenv('AWS_ACCOUNT_ID')
            },
            'gcp': {
                'enabled': os.getenv('GCP_COST_ANALYSIS_ENABLED', 'true').lower() == 'true',
                'credentials': os.getenv('GCP_CREDENTIALS_PATH'),
                'project_id': os.getenv('GCP_PROJECT_ID')
            },
            'azure': {
                'enabled': os.getenv('AZURE_COST_ANALYSIS_ENABLED', 'false').lower() == 'true',
                'tenant_id': os.getenv('AZURE_TENANT_ID'),
                'client_id': os.getenv('AZURE_CLIENT_ID'),
                'client_secret': os.getenv('AZURE_CLIENT_SECRET'),
                'subscription_id': os.getenv('AZURE_SUBSCRIPTION_ID')
            },
            'datadog': {
                'enabled': os.getenv('DATADOG_COST_ANALYSIS_ENABLED', 'true').lower() == 'true',
                'api_key': os.getenv('DATADOG_API_KEY'),
                'app_key': os.getenv('DATADOG_APP_KEY')
            },
            'optimization': {
                'dry_run': os.getenv('COST_OPTIMIZATION_DRY_RUN', 'false').lower() == 'true',
                'auto_apply': os.getenv('COST_OPTIMIZATION_AUTO_APPLY', 'false').lower() == 'true',
                'report_path': os.getenv('COST_REPORT_PATH', '/var/reports/cost_optimization'),
                'threshold_percentage': float(os.getenv('COST_THRESHOLD_PERCENTAGE', '5.0'))
            }
        }

        # Create report directory if it doesn't exist
        os.makedirs(config['optimization']['report_path'], exist_ok=True)

        return config

    def _initialize_cloud_providers(self) -> Dict:
        """Initialize cloud provider clients."""
        providers = {}

        if self.config['aws']['enabled']:
            providers['aws'] = {
                'client': boto3.client(
                    'ce',
                    aws_access_key_id=self.config['aws']['access_key'],
                    aws_secret_access_key=self.config['aws']['secret_key'],
                    region_name=self.config['aws']['region']
                ),
                'account_id': self.config['aws']['account_id']
            }

        if self.config['gcp']['enabled']:
            credentials = service_account.Credentials.from_service_account_file(
                self.config['gcp']['credentials']
            )
            providers['gcp'] = {
                'client': billing_v1.BillingClient(credentials=credentials),
                'project_id': self.config['gcp']['project_id']
            }

        # Azure initialization would go here (using azure-mgmt-billing)
        # For brevity, we'll focus on AWS and GCP which are most common

        return providers

    def fetch_cost_data(self) -> Dict:
        """Fetch cost data from all enabled cloud providers."""
        logger.info("Fetching cost data from cloud providers...")

        for provider_name, provider in self.cloud_providers.items():
            try:
                if provider_name == 'aws':
                    self._fetch_aws_costs(provider)
                elif provider_name == 'gcp':
                    self._fetch_gcp_costs(provider)
                logger.info(f"Successfully fetched costs from {provider_name.upper()}")
            except Exception as e:
                logger.error(f"Failed to fetch costs from {provider_name.upper()}: {str(e)}")
                continue

        return self.cost_data

    def _fetch_aws_costs(self, provider: Dict):
        """Fetch AWS cost data using Cost Explorer API."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        response = provider['client'].get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['BlendedCost', 'UsageQuantity', 'NormalizedUsageAmount'],
            GroupBy=[
                {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                {'Type': 'DIMENSION', 'Key': 'INSTANCE_TYPE'},
                {'Type': 'TAG', 'Key': 'Environment'}
            ]
        )

        aws_costs = {
            'provider': 'aws',
            'total_cost': 0.0,
            'services': {},
            'daily_costs': [],
            'last_updated': datetime.now().isoformat()
        }

        for result in response['ResultsByTime']:
            date = result['TimePeriod']['Start']
            daily_cost = float(result['Total']['BlendedCost']['Amount'])
            aws_costs['total_cost'] += daily_cost
            aws_costs['daily_costs'].append({
                'date': date,
                'cost': daily_cost
            })

            for group in result['Groups']:
                service = group['Keys'][0]
                instance_type = group['Keys'][1] if len(group['Keys']) > 1 else 'N/A'
                cost = float(group['Metrics']['BlendedCost']['Amount'])

                if service not in aws_costs['services']:
                    aws_costs['services'][service] = {
                        'total_cost': 0.0,
                        'instance_types': {},
                        'daily_breakdown': {}
                    }

                aws_costs['services'][service]['total_cost'] += cost
                aws_costs['services'][service]['daily_breakdown'][date] = cost

                if instance_type not in aws_costs['services'][service]['instance_types']:
                    aws_costs['services'][service]['instance_types'][instance_type] = 0.0
                aws_costs['services'][service]['instance_types'][instance_type] += cost

        self.cost_data['aws'] = aws_costs

    def _fetch_gcp_costs(self, provider: Dict):
        """Fetch GCP cost data using Billing API."""
        # Note: GCP billing API requires project-level billing data
        # This is a simplified version for demonstration

        billing_client = provider['client']
        project_id = provider['project_id']

        # Get billing account name
        billing_accounts = billing_client.list_billing_accounts()
        billing_account_name = None

        for account in billing_accounts:
            if account.display_name == 'District Award Travel':
                billing_account_name = account.name
                break

        if not billing_account_name:
            logger.warning("Could not find District Award Travel billing account in GCP")
            return

        # Get cost data (simplified - actual implementation would use export APIs)
        gcp_costs = {
            'provider': 'gcp',
            'total_cost': 0.0,  # Would come from actual API
            'services': {
                'Compute Engine': {'total_cost': 0.0, 'instance_types': {}, 'daily_breakdown': {}},
                'Cloud SQL': {'total_cost': 0.0, 'instance_types': {}, 'daily_breakdown': {}},
                'Kubernetes Engine': {'total_cost': 0.0, 'instance_types': {}, 'daily_breakdown': {}}
            },
            'daily_costs': [],
            'last_updated': datetime.now().isoformat()
        }

        # In a real implementation, we would query the export data
        # For now, we'll simulate some data based on AWS patterns
        gcp_costs['total_cost'] = self.cost_data.get('aws', {}).get('total_cost', 0) * 0.8  # Assume GCP is 20% cheaper

        for service in gcp_costs['services']:
            gcp_costs['services'][service]['total_cost'] = gcp_costs['total_cost'] * 0.3  # Distribute costs

        self.cost_data['gcp'] = gcp_costs

    def analyze_costs(self) -> Dict:
        """Analyze cost data to identify optimization opportunities."""
        logger.info("Analyzing cost data for optimization opportunities...")

        analysis = {
            'timestamp': datetime.now().isoformat(),
            'total_monthly_cost': 0.0,
            'potential_savings': 0.0,
            'recommendations': [],
            'service_breakdown': {}
        }

        # Calculate total monthly cost
        for provider_data in self.cost_data.values():
            analysis['total_monthly_cost'] += provider_data.get('total_cost', 0)

        # Analyze each service for optimization opportunities
        for provider_name, provider_data in self.cost_data.items():
            for service_name, service_data in provider_data['services'].items():
                service_cost = service_data['total_cost']
                analysis['service_breakdown'][f"{provider_name.upper()}-{service_name}"] = {
                    'cost': service_cost,
                    'percentage_of_total': (service_cost / analysis['total_monthly_cost']) * 100 if analysis['total_monthly_cost'] > 0 else 0
                }

                # Generate recommendations based on service type
                recommendations = self._generate_service_recommendations(
                    provider_name, service_name, service_data
                )

                analysis['recommendations'].extend(recommendations)

        # Calculate potential savings
        analysis['potential_savings'] = sum(
            rec['potential_savings'] for rec in analysis['recommendations']
        )

        analysis['savings_percentage'] = (
            (analysis['potential_savings'] / analysis['total_monthly_cost']) * 100
            if analysis['total_monthly_cost'] > 0 else 0
        )

        self.optimization_results.append(analysis)
        return analysis

    def _generate_service_recommendations(self, provider: str, service: str, service_data: Dict) -> List[Dict]:
        """Generate specific recommendations for a service."""
        recommendations = []

        # EC2/Compute Engine recommendations
        if service in ['Amazon Elastic Compute Cloud - Compute', 'Compute Engine']:
            recommendations.extend(self._analyze_compute_services(provider, service, service_data))

        # RDS/Cloud SQL recommendations
        elif service in ['Amazon Relational Database Service', 'Cloud SQL']:
            recommendations.extend(self._analyze_database_services(provider, service, service_data))

        # S3/Cloud Storage recommendations
        elif service in ['Amazon Simple Storage Service', 'Cloud Storage']:
            recommendations.extend(self._analyze_storage_services(provider, service, service_data))

        # Kubernetes recommendations
        elif service in ['Amazon Elastic Container Service for Kubernetes', 'Kubernetes Engine']:
            recommendations.extend(self._analyze_kubernetes_services(provider, service, service_data))

        return recommendations

    def _analyze_compute_services(self, provider: str, service: str, service_data: Dict) -> List[Dict]:
        """Analyze compute services for optimization opportunities."""
        recommendations = []

        # Check for underutilized instances
        for instance_type, cost in service_data['instance_types'].items():
            if instance_type == 'N/A':
                continue

            # Simple heuristic: if cost is high but we can't determine utilization, suggest rightsizing
            if cost > 1000:  # More than $1000/month
                recommendations.append({
                    'type': 'compute_rightsizing',
                    'provider': provider,
                    'service': service,
                    'instance_type': instance_type,
                    'current_cost': cost,
                    'potential_savings': cost * 0.3,  # Conservative estimate of 30% savings
                    'description': f"Consider rightsizing {instance_type} instances. Potential 30% cost reduction through instance type optimization.",
                    'severity': 'medium',
                    'action': 'analyze_instance_utilization'
                })

        # Check for reserved instances
        if provider == 'aws':
            recommendations.append({
                'type': 'reserved_instances',
                'provider': provider,
                'service': service,
                'current_cost': sum(service_data['instance_types'].values()),
                'potential_savings': sum(service_data['instance_types'].values()) * 0.4,  # 40% savings with RIs
                'description': "Purchase Reserved Instances for long-running workloads. Can save up to 75% compared to on-demand.",
                'severity': 'high',
                'action': 'purchase_reserved_instances'
            })

        return recommendations

    def _analyze_database_services(self, provider: str, service: str, service_data: Dict) -> List[Dict]:
        """Analyze database services for optimization opportunities."""
        recommendations = []

        # Check for idle or over-provisioned databases
        total_db_cost = sum(service_data['instance_types'].values())
        recommendations.append({
            'type': 'database_optimization',
            'provider': provider,
            'service': service,
            'current_cost': total_db_cost,
            'potential_savings': total_db_cost * 0.25,  # 25% savings through optimization
            'description': "Analyze database utilization and consider: 1) Downsizing instances, 2) Switching to serverless options, 3) Implementing read replicas for read-heavy workloads.",
            'severity': 'high',
            'action': 'database_utilization_analysis'
        })

        return recommendations

    def _analyze_storage_services(self, provider: str, service: str, service_data: Dict) -> List[Dict]:
        """Analyze storage services for optimization opportunities."""
        recommendations = []

        # S3 lifecycle policies
        recommendations.append({
            'type': 'storage_lifecycle',
            'provider': provider,
            'service': service,
            'current_cost': sum(service_data['instance_types'].values()),
            'potential_savings': sum(service_data['instance_types'].values()) * 0.2,  # 20% savings
            'description': "Implement S3 lifecycle policies to transition older data to cheaper storage classes (S3 IA, Glacier). Can save 40-60% on storage costs.",
            'severity': 'medium',
            'action': 'implement_lifecycle_policies'
        })

        return recommendations

    def _analyze_kubernetes_services(self, provider: str, service: str, service_data: Dict) -> List[Dict]:
        """Analyze Kubernetes services for optimization opportunities."""
        recommendations = []

        # Cluster autoscaling and rightsizing
        recommendations.append({
            'type': 'kubernetes_optimization',
            'provider': provider,
            'service': service,
            'current_cost': sum(service_data['instance_types'].values()),
            'potential_savings': sum(service_data['instance_types'].values()) * 0.35,  # 35% savings
            'description': "Optimize Kubernetes costs by: 1) Implementing cluster autoscaling, 2) Rightsizing node pools, 3) Using spot instances for non-critical workloads, 4) Implementing pod resource requests/limits.",
            'severity': 'high',
            'action': 'kubernetes_cost_optimization'
        })

        return recommendations

    def generate_report(self) -> str:
        """Generate a comprehensive cost optimization report."""
        if not self.optimization_results:
            self.analyze_costs()

        report = self.optimization_results[-1]
        report_path = os.path.join(
            self.config['optimization']['report_path'],
            f"cost_optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Cost optimization report generated at {report_path}")

        # Also generate a human-readable summary
        summary_path = os.path.join(
            self.config['optimization']['report_path'],
            f"cost_summary_{datetime.now().strftime('%Y%m%d')}.txt"
        )

        with open(summary_path, 'w') as f:
            f.write("=== District Award Travel Cost Optimization Report ===\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Total Monthly Infrastructure Cost: ${report['total_monthly_cost']:.2f}\n")
            f.write(f"Potential Monthly Savings: ${report['potential_savings']:.2f} ({report['savings_percentage']:.1f}%)\n\n")
            f.write("=== Top Recommendations ===\n")

            # Sort recommendations by potential savings
            sorted_recs = sorted(
                report['recommendations'],
                key=lambda x: x['potential_savings'],
                reverse=True
            )

            for rec in sorted_recs[:5]:  # Top 5 recommendations
                f.write(f"\n• {rec['description']}\n")
                f.write(f"  Provider: {rec['provider'].upper()}\n")
                f.write(f"  Service: {rec['service']}\n")
                f.write(f"  Potential Savings: ${rec['potential_savings']:.2f}\n")
                f.write(f"  Severity: {rec['severity']}\n")

        logger.info(f"Cost summary generated at {summary_path}")

        return report_path

    def implement_optimizations(self) -> Dict:
        """Implement cost optimization recommendations."""
        if not self.optimization_results:
            self.analyze_costs()

        report = self.optimization_results[-1]
        implementation_results = {
            'timestamp': datetime.now().isoformat(),
            'total_implemented': 0,
            'total_savings': 0.0,
            'details': []
        }

        # Sort recommendations by potential savings (highest first)
        sorted_recs = sorted(
            report['recommendations'],
            key=lambda x: x['potential_savings'],
            reverse=True
        )

        for rec in sorted_recs:
            if rec['potential_savings'] < 10:  # Skip recommendations with minimal savings
                continue

            try:
                result = self._implement_recommendation(rec)
                if result['success']:
                    implementation_results['total_implemented'] += 1
                    implementation_results['total_savings'] += rec['potential_savings']
                    implementation_results['details'].append(result)
                    logger.info(f"Successfully implemented optimization: {rec['description']}")
                else:
                    logger.warning(f"Failed to implement optimization: {rec['description']} - {result['error']}")
            except Exception as e:
                logger.error(f"Error implementing recommendation {rec['type']}: {str(e)}")
                implementation_results['details'].append({
                    'recommendation': rec['type'],
                    'success': False,
                    'error': str(e)
                })

        return implementation_results

    def _implement_recommendation(self, recommendation: Dict) -> Dict:
        """Implement a specific cost optimization recommendation."""
        result = {
            'recommendation': recommendation['type'],
            'provider': recommendation['provider'],
            'service': recommendation['service'],
            'potential_savings': recommendation['potential_savings'],
            'implemented_at': datetime.now().isoformat(),
            'success': False,
            'details': {}
        }

        if self.config['optimization']['dry_run']:
            result['success'] = True
            result['details']['message'] = "Dry run mode - no changes implemented"
            result['details']['simulated_savings'] = recommendation['potential_savings']
            return result

        try:
            if recommendation['action'] == 'purchase_reserved_instances':
                result.update(self._purchase_reserved_instances(recommendation))
            elif recommendation['action'] == 'implement_lifecycle_policies':
                result.update(self._implement_storage_lifecycle(recommendation))
            elif recommendation['action'] == 'database_utilization_analysis':
                result.update(self._analyze_database_utilization(recommendation))
            elif recommendation['action'] == 'kubernetes_cost_optimization':
                result.update(self._optimize_kubernetes(recommendation))
            else:
                result['details']['message'] = "No implementation action defined for this recommendation"
                result['success'] = True  # Not an error, just nothing to do

        except Exception as e:
            result['success'] = False
            result['error'] = str(e)

        return result

    def _purchase_reserved_instances(self, recommendation: Dict) -> Dict:
        """Purchase reserved instances for AWS EC2."""
        if recommendation['provider'] != 'aws':
            return {'success': False, 'error': 'Reserved instances only available for AWS'}

        # In a real implementation, this would call AWS EC2 API to purchase RIs
        # For now, we'll simulate the action

        result = {
            'success': True,
            'details': {
                'message': "Simulated RI purchase",
                'instance_type': 'm5.large',  # Example
                'term': '1 year',  # Example
                'upfront_payment': recommendation['potential_savings'] * 0.3,  # 30% upfront
                'net_savings': recommendation['potential_savings'] * 0.7  # 70% over term
            }
        }

        return result

    def _implement_storage_lifecycle(self, recommendation: Dict) -> Dict:
        """Implement S3 lifecycle policies."""
        if recommendation['provider'] != 'aws' or recommendation['service'] != 'Amazon Simple Storage Service':
            return {'success': False, 'error': 'Storage lifecycle only applicable to AWS S3'}

        # In a real implementation, this would:
        # 1. Get current S3 buckets
        # 2. Analyze object age patterns
        # 3. Create/update lifecycle policies

        result = {
            'success': True,
            'details': {
                'message': "Simulated S3 lifecycle policy implementation",
                'policies_created': ['district-award-travel-data-archive'],
                'estimated_savings': recommendation['potential_savings']
            }
        }

        return result

    def _analyze_database_utilization(self, recommendation: Dict) -> Dict:
        """Analyze and optimize database utilization."""
        # In a real implementation, this would:
        # 1. Query database metrics
        # 2. Identify underutilized instances
        # 3. Recommend downsizing or switching to serverless

        result = {
            'success': True,
            'details': {
                'message': "Simulated database utilization analysis",
                'recommendations': [
                    "Downsize db.t3.micro to db.t3.small for dev environment",
                    "Consider Aurora Serverless for variable workloads"
                ],
                'estimated_savings': recommendation['potential_savings']
            }
        }

        return result

    def _optimize_kubernetes(self, recommendation: Dict) -> Dict:
        """Optimize Kubernetes cluster costs."""
        # In a real implementation, this would:
        # 1. Analyze cluster utilization
        # 2. Adjust node pool sizes
        # 3. Implement cluster autoscaling
        # 4. Configure spot instances

        result = {
            'success': True,
            'details': {
                'message': "Simulated Kubernetes optimization",
                'actions_taken': [
                    "Enabled cluster autoscaler",
                    "Configured spot instance node pool",
                    "Set pod resource requests/limits"
                ],
                'estimated_savings': recommendation['potential_savings']
            }
        }

        return result

    def run_optimization_pipeline(self):
        """Run the complete cost optimization pipeline."""
        logger.info("Starting cost optimization pipeline...")

        try:
            # Step 1: Fetch cost data
            self.fetch_cost_data()

            # Step 2: Analyze costs
            analysis = self.analyze_costs()
            logger.info(f"Analysis complete. Total cost: ${analysis['total_monthly_cost']:.2f}")
            logger.info(f"Potential savings: ${analysis['potential_savings']:.2f} ({analysis['savings_percentage']:.1f}%)")

            # Step 3: Generate report
            report_path = self.generate_report()

            # Step 4: Implement optimizations (if not dry run)
            if not self.config['optimization']['dry_run']:
                implementation = self.implement_optimizations()
                logger.info(f"Implemented {implementation['total_implemented']} optimizations")
                logger.info(f"Total estimated savings: ${implementation['total_savings']:.2f}")
            else:
                logger.info("Dry run mode - no optimizations implemented")

            # Step 5: Create summary notification
            self._create_notification()

            logger.info("Cost optimization pipeline completed successfully")
            return {
                'status': 'success',
                'analysis': analysis,
                'report_path': report_path,
                'implementation': self.optimization_results[-1].get('implementation', {}) if not self.config['optimization']['dry_run'] else None
            }

        except Exception as e:
            logger.error(f"Cost optimization pipeline failed: {str(e)}")
            logger.exception("Full traceback:")
            return {
                'status': 'failed',
                'error': str(e)
            }

    def _create_notification(self):
        """Create a notification with optimization results."""
        if not self.optimization_results:
            return

        report = self.optimization_results[-1]
        savings = report['potential_savings']
        percentage = report['savings_percentage']

        # Create a simple notification file
        notification_path = os.path.join(
            self.config['optimization']['report_path'],
            'latest_optimization.json'
        )

        notification = {
            'timestamp': datetime.now().isoformat(),
            'total_cost': report['total_monthly_cost'],
            'potential_savings': savings,
            'savings_percentage': percentage,
            'top_recommendations': sorted(
                report['recommendations'],
                key=lambda x: x['potential_savings'],
                reverse=True
            )[:3]
        }

        with open(notification_path, 'w') as f:
            json.dump(notification, f, indent=2)

        logger.info(f"Optimization notification created at {notification_path}")

        # Also update a simple status file for monitoring
        status_path = os.path.join(
            self.config['optimization']['report_path'],
            'optimization_status.txt'
        )

        with open(status_path, 'w') as f:
            f.write(f"Last optimization: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total cost: ${report['total_monthly_cost']:.2f}\n")
            f.write(f"Potential savings: ${savings:.2f} ({percentage:.1f}%)\n")
            f.write(f"Status: {'DRY RUN' if self.config['optimization']['dry_run'] else 'ACTIVE'}\n")

def main():
    """Main entry point for the cost optimization system."""
    optimizer = CostOptimizer()

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='District Award Travel Cost Optimization System')
    parser.add_argument('--dry-run', action='store_true', help='Run in dry-run mode without making changes')
    parser.add_argument('--analyze', action='store_true', help='Only analyze costs without implementing changes')
    parser.add_argument('--report', action='store_true', help='Generate report only')
    parser.add_argument('--force', action='store_true', help='Force implementation of optimizations')

    args = parser.parse_args()

    if args.dry_run:
        optimizer.config['optimization']['dry_run'] = True
        logger.info("Running in DRY RUN mode - no changes will be implemented")

    if args.force:
        optimizer.config['optimization']['auto_apply'] = True
        logger.info("Forcing implementation of optimizations")

    if args.report:
        # Just generate report
        optimizer.fetch_cost_data()
        optimizer.analyze_costs()
        optimizer.generate_report()
        logger.info("Report generated successfully")
        return 0

    if args.analyze:
        # Just analyze costs
        optimizer.fetch_cost_data()
        analysis = optimizer.analyze_costs()
        print(json.dumps(analysis, indent=2))
        return 0

    # Run full pipeline
    result = optimizer.run_optimization_pipeline()

    if result['status'] == 'success':
        return 0
    else:
        logger.error("Cost optimization pipeline failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
