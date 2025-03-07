import streamlit as st
import pandas as pd
import plotly.express as px
import json
import sqlite3
from typing import Dict, List
import datetime
from database import getAllPapers
from taxonomyProcessor import TaxonomyProcessor

class ReportGenerator:
    """Generates summary reports and visualizations for research papers"""
    
    def __init__(self):
        """Initialize the report generator"""
        self.taxonomyProcessor = TaxonomyProcessor()
        
    def generateSummaryReport(self) -> Dict:
        """
        Generate a comprehensive summary report of all papers in the database
        
        Returns:
            Dictionary containing report data
        """
        # Get all papers and their metadata
        papers = getAllPapers()
        taxonomies = self.taxonomyProcessor.getAllTaxonomies()
        
        # If no papers, return empty report
        if not papers:
            return {
                "totalPapers": 0,
                "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "fields": {},
                "recentPapers": []
            }
        
        # Create a mapping of paper IDs to taxonomies
        taxonomyMap = {tax["paperId"]: tax for tax in taxonomies}
        
        # Get field statistics
        fieldStats = self.taxonomyProcessor.getFieldStatistics()
        
        # Count papers by field
        fieldCounts = {}
        for paper in papers:
            paperId = paper["id"]
            if paperId in taxonomyMap:
                primaryField = taxonomyMap[paperId]["primaryField"]
                if primaryField not in fieldCounts:
                    fieldCounts[primaryField] = 0
                fieldCounts[primaryField] += 1
        
        # Get most recent papers (up to 5)
        recentPapers = papers[:5]  # Assuming papers are already sorted by recency
        
        return {
            "totalPapers": len(papers),
            "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fields": fieldStats,
            "fieldCounts": fieldCounts,
            "recentPapers": recentPapers
        }
    
    def generateFieldReport(self, fieldName: str) -> Dict:
        """
        Generate a report for a specific research field
        
        Args:
            fieldName: The name of the field to report on
            
        Returns:
            Dictionary containing field report data
        """
        # Get papers in this field
        papersInField = self.taxonomyProcessor.getPapersByField(fieldName)
        
        if not papersInField:
            return {
                "fieldName": fieldName,
                "paperCount": 0,
                "papers": []
            }
        
        # Count subfields
        subfieldCounts = {}
        for paper in papersInField:
            if "taxonomy" in paper and "subfields" in paper["taxonomy"]:
                for subfield in paper["taxonomy"]["subfields"]:
                    if subfield not in subfieldCounts:
                        subfieldCounts[subfield] = 0
                    subfieldCounts[subfield] += 1
        
        # Get application analysis for these papers
        applications = self._getApplicationAnalysisForPapers([p["id"] for p in papersInField])
        
        # Compile commercial potential by industry
        commercialPotential = {}
        for paperId, appData in applications.items():
            if "industryApplications" in appData:
                for industry in appData["industryApplications"]:
                    industryName = industry["industryName"]
                    if industryName not in commercialPotential:
                        commercialPotential[industryName] = {"low": 0, "medium": 0, "high": 0}
                    potential = industry["commercialPotential"]
                    commercialPotential[industryName][potential] += 1
        
        return {
            "fieldName": fieldName,
            "paperCount": len(papersInField),
            "subfieldCounts": subfieldCounts,
            "papers": papersInField,
            "commercialPotential": commercialPotential
        }
    
    def _getApplicationAnalysisForPapers(self, paperIds: List[str]) -> Dict:
        """
        Get application analysis for multiple papers
        
        Args:
            paperIds: List of paper IDs to get analysis for
            
        Returns:
            Dictionary mapping paper IDs to their application analysis
        """
        conn = sqlite3.connect('data/metadata.db')
        c = conn.cursor()
        
        # Check if application_analysis table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='application_analysis'")
        if not c.fetchone():
            conn.close()
            return {}
        
        # Get application analysis for each paper
        results = {}
        for paperId in paperIds:
            c.execute("SELECT * FROM application_analysis WHERE paper_id=?", (paperId,))
            row = c.fetchone()
            if row:
                results[paperId] = {
                    "industryApplications": json.loads(row[1]),
                    "academicApplications": json.loads(row[2]),
                    "overallCommercialValue": row[3],
                    "interdisciplinaryPotential": row[4]
                }
        
        conn.close()
        return results
    
    def renderSummaryPage(self):
        """Render a summary page with visualizations in Streamlit"""
        st.title("Research Overview Summary")
        
        # Generate summary report
        report = self.generateSummaryReport()
        
        # Display basic statistics
        st.header("Overview")
        col1, col2 = st.columns(2)
        col1.metric("Total Papers", report["totalPapers"])
        col2.metric("Total Research Fields", len(report.get("fieldCounts", {})))
        
        st.caption(f"Report generated at: {report['generatedAt']}")
        
        # Display field distribution
        st.header("Research Field Distribution")
        
        if report.get("fieldCounts"):
            # Create DataFrame for field counts
            fieldDf = pd.DataFrame({
                "Field": list(report["fieldCounts"].keys()),
                "Paper Count": list(report["fieldCounts"].values())
            })
            
            # Sort by paper count in descending order
            fieldDf = fieldDf.sort_values("Paper Count", ascending=False)
            
            # Create bar chart
            fig = px.bar(
                fieldDf, 
                x="Field", 
                y="Paper Count", 
                title="Papers by Research Field",
                color="Paper Count",
                color_continuous_scale="Viridis"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No field data available.")
        
        # Display subfields word cloud or bar chart
        st.header("Top Research Subfields")
        
        if report.get("fields", {}).get("subfields"):
            # Create DataFrame for subfields
            subfields = report["fields"]["subfields"]
            subfieldDf = pd.DataFrame({
                "Subfield": list(subfields.keys()),
                "Count": list(subfields.values())
            })
            
            # Sort by count in descending order
            subfieldDf = subfieldDf.sort_values("Count", ascending=False).head(10)
            
            # Create bar chart
            fig = px.bar(
                subfieldDf, 
                x="Subfield", 
                y="Count", 
                title="Top 10 Research Subfields",
                color="Count",
                color_continuous_scale="Viridis"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No subfield data available.")
        
        # Display recent papers
        st.header("Recent Papers")
        
        if report.get("recentPapers"):
            for i, paper in enumerate(report["recentPapers"]):
                with st.expander(f"{i+1}. {paper['title']}", expanded=i==0):
                    st.write(f"**Summary**: {paper['summary']}")
                    st.write(f"**Authors**: {', '.join(paper['authors'])}")
                    if paper.get('link'):
                        st.write(f"**Link**: [{paper['link']}]({paper['link']})")
        else:
            st.info("No papers available.")
    
    def renderFieldReportPage(self, fieldName: str):
        """
        Render a detailed report page for a specific field in Streamlit
        
        Args:
            fieldName: The name of the field to report on
        """
        st.title(f"Research Field Report: {fieldName}")
        
        # Generate field report
        report = self.generateFieldReport(fieldName)
        
        if report["paperCount"] == 0:
            st.info(f"No papers found in the {fieldName} field.")
            return
        
        # Display basic statistics
        st.header("Overview")
        st.metric("Papers in this field", report["paperCount"])
        
        # Display subfields
        st.header("Subfields")
        
        if report.get("subfieldCounts"):
            # Create DataFrame for subfields
            subfieldDf = pd.DataFrame({
                "Subfield": list(report["subfieldCounts"].keys()),
                "Count": list(report["subfieldCounts"].values())
            })
            
            # Sort by count in descending order
            subfieldDf = subfieldDf.sort_values("Count", ascending=False)
            
            # Create bar chart
            fig = px.bar(
                subfieldDf, 
                x="Subfield", 
                y="Count", 
                title=f"Subfields in {fieldName}",
                color="Count",
                color_continuous_scale="Viridis"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No subfield data available.")
        
        # Display commercial potential
        st.header("Commercial Potential by Industry")
        
        if report.get("commercialPotential"):
            # Transform the data for visualization
            industries = []
            potentials = []
            counts = []
            
            for industry, potentialCounts in report["commercialPotential"].items():
                for potential, count in potentialCounts.items():
                    if count > 0:
                        industries.append(industry)
                        potentials.append(potential)
                        counts.append(count)
            
            # Create DataFrame
            potentialDf = pd.DataFrame({
                "Industry": industries,
                "Potential": potentials,
                "Count": counts
            })
            
            # Create grouped bar chart
            fig = px.bar(
                potentialDf, 
                x="Industry", 
                y="Count", 
                color="Potential",
                title=f"Commercial Potential by Industry for {fieldName}",
                color_discrete_map={"high": "green", "medium": "yellow", "low": "red"}
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No commercial potential data available.")
        
        # Display papers in this field
        st.header("Papers in this Field")
        
        for i, paper in enumerate(report["papers"]):
            with st.expander(f"{i+1}. {paper['title']}", expanded=False):
                st.write(f"**Summary**: {paper['summary']}")
                st.write(f"**Authors**: {', '.join(paper['authors'])}")
                if paper.get('link'):
                    st.write(f"**Link**: [{paper['link']}]({paper['link']})")
                
                # Display taxonomy if available
                if "taxonomy" in paper:
                    st.write("**Taxonomy**:")
                    st.write(f"- Primary Field: {paper['taxonomy']['primaryField']}")
                    st.write(f"- Secondary Fields: {', '.join(paper['taxonomy']['secondaryFields'])}")
                    st.write(f"- Subfields: {', '.join(paper['taxonomy']['subfields'])}")
    
    def generateHtmlReport(self) -> str:
        """
        Generate an HTML report summarizing all research fields and applications
        
        Returns:
            String containing HTML document
        """
        # Generate summary report
        report = self.generateSummaryReport()
        
        # Generate field reports for top fields
        fieldReports = {}
        for fieldName in list(report.get("fieldCounts", {}).keys())[:5]:  # Top 5 fields
            fieldReports[fieldName] = self.generateFieldReport(fieldName)
        
        # Build HTML report
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Research Overview Report</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    color: #333;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                h1, h2, h3 {{
                    color: #2C3E50;
                }}
                .card {{
                    background-color: #f9f9f9;
                    border-radius: 8px;
                    padding: 20px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .stats {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .stat-card {{
                    background-color: #fff;
                    border-radius: 8px;
                    padding: 20px;
                    min-width: 200px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    flex: 1;
                }}
                .stat-card h3 {{
                    margin-top: 0;
                    color: #3498DB;
                }}
                .stat-value {{
                    font-size: 32px;
                    font-weight: bold;
                    margin: 10px 0;
                }}
                .chart {{
                    width: 100%;
                    height: 400px;
                    margin-bottom: 30px;
                }}
                .paper-card {{
                    background-color: #fff;
                    border-left: 4px solid #3498DB;
                    padding: 15px;
                    margin-bottom: 15px;
                }}
                .paper-title {{
                    margin-top: 0;
                    color: #2C3E50;
                }}
                .metadata {{
                    color: #7f8c8d;
                    font-size: 14px;
                    margin-bottom: 10px;
                }}
                footer {{
                    margin-top: 50px;
                    text-align: center;
                    color: #7f8c8d;
                    font-size: 14px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Research Overview Report</h1>
                <p>Generated on {report["generatedAt"]}</p>
                
                <div class="card">
                    <h2>Summary Statistics</h2>
                    <div class="stats">
                        <div class="stat-card">
                            <h3>Total Papers</h3>
                            <div class="stat-value">{report["totalPapers"]}</div>
                        </div>
                        <div class="stat-card">
                            <h3>Research Fields</h3>
                            <div class="stat-value">{len(report.get("fieldCounts", {}))}</div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h2>Research Field Distribution</h2>
                    <div id="fieldChart" class="chart"></div>
                </div>
        """
        
        # Add section for each top field
        for fieldName, fieldReport in fieldReports.items():
            html += f"""
                <div class="card">
                    <h2>{fieldName}</h2>
                    <p>{fieldReport["paperCount"]} papers in this field</p>
                    
                    <h3>Subfields</h3>
                    <div id="subfield_{fieldName.replace(' ', '_')}" class="chart"></div>
                    
                    <h3>Recent Papers in {fieldName}</h3>
            """
            
            # Add up to 3 papers for this field
            for i, paper in enumerate(fieldReport["papers"][:3]):
                authors = ", ".join(paper["authors"]) if paper.get("authors") else "Unknown"
                html += f"""
                    <div class="paper-card">
                        <h3 class="paper-title">{paper["title"]}</h3>
                        <div class="metadata">Authors: {authors}</div>
                        <p>{paper["summary"][:300]}...</p>
                    </div>
                """
                
            html += """
                </div>
            """
        
        # Add JavaScript for charts
        html += """
                <footer>
                    <p>Generated by ResearchOverviewAI</p>
                </footer>
            </div>
            
            <script>
        """
        
        # Add field distribution chart
        if report.get("fieldCounts"):
            fields = list(report["fieldCounts"].keys())
            counts = list(report["fieldCounts"].values())
            
            html += f"""
                // Field distribution chart
                var fieldData = [{{
                    x: {json.dumps(fields)},
                    y: {json.dumps(counts)},
                    type: 'bar',
                    marker: {{
                        color: 'rgba(55, 128, 191, 0.7)',
                        line: {{
                            color: 'rgba(55, 128, 191, 1.0)',
                            width: 2
                        }}
                    }}
                }}];
                
                var fieldLayout = {{
                    title: 'Papers by Research Field',
                    xaxis: {{ title: 'Field' }},
                    yaxis: {{ title: 'Paper Count' }}
                }};
                
                Plotly.newPlot('fieldChart', fieldData, fieldLayout);
            """
        
        # Add subfield charts for each field
        for fieldName, fieldReport in fieldReports.items():
            if fieldReport.get("subfieldCounts"):
                subfields = list(fieldReport["subfieldCounts"].keys())
                counts = list(fieldReport["subfieldCounts"].values())
                
                chartId = f"subfield_{fieldName.replace(' ', '_')}"
                
                html += f"""
                    // Subfield chart for {fieldName}
                    var {chartId}Data = [{{
                        x: {json.dumps(subfields)},
                        y: {json.dumps(counts)},
                        type: 'bar',
                        marker: {{
                            color: 'rgba(50, 171, 96, 0.7)',
                            line: {{
                                color: 'rgba(50, 171, 96, 1.0)',
                                width: 2
                            }}
                        }}
                    }}];
                    
                    var {chartId}Layout = {{
                        title: 'Subfields in {fieldName}',
                        xaxis: {{ title: 'Subfield' }},
                        yaxis: {{ title: 'Count' }}
                    }};
                    
                    Plotly.newPlot('{chartId}', {chartId}Data, {chartId}Layout);
                """
        
        # Close HTML document
        html += """
            </script>
        </body>
        </html>
        """
        
        return html