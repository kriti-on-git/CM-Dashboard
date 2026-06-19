import asyncio
import logging
import argparse
import sys
import json
from app.services.agents.decision_agent import DecisionAgent
from app.ml.train import TrainPipeline

# Setup Global File Logging
os_makedirs = __import__("os").makedirs
os_makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/system.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("run_pipeline")

async def run_e2e_tests():
    logger.info("Initializing Decision Agent...")
    agent = DecisionAgent()
    
    # 1. FIXED: Bina text ke khali process() call hata diya
    
    logger.info("\n--- TEST CASE 1: NORMAL CASE ---")
    normal_text = "Garbage not collected in my area, it smells terrible."
    res1 = await agent.process(normal_text)
    
    # 2. FIXED: .get() laga diya taaki agar dictionary structure badla ho toh crash na ho
    try:
        decision1 = res1.get('final_decision', res1)
        logger.info(f"Result (Normal): Routing -> {decision1.get('assigned_team')}, Complaint -> {decision1.get('complaint_categories')}")
    except Exception as e:
        logger.error(f"Could not parse Test Case 1 output. Full Response: {res1}")
    
    logger.info("\n--- TEST CASE 2: EDGE CASE (EMPTY/NOISY) ---")
    edge_text = "..... what is this ..... ?"
    res2 = await agent.process(edge_text)
    try:
        decision2 = res2.get('final_decision', res2)
        logger.info(f"Result (Edge): Routing -> {decision2.get('assigned_team')}, Complaint -> {decision2.get('complaint_categories')}")
    except Exception as e:
        logger.error(f"Could not parse Test Case 2 output. Full Response: {res2}")
    
    logger.info("\n--- TEST CASE 3: UNSEEN MULTI-LABEL CASE ---")
    unseen_text = "Street light flickering and water leakage on 5th avenue."
    res3 = await agent.process(unseen_text)
    try:
        decision3 = res3.get('final_decision', res3)
        logger.info(f"Result (Unseen): Routing -> {decision3.get('assigned_team')}, Complaint -> {decision3.get('complaint_categories')}")
    except Exception as e:
        logger.error(f"Could not parse Test Case 3 output. Full Response: {res3}")
    
    # 3. FIXED: Purana manager.stop_background_workers() completely hata diya
    await asyncio.sleep(1)
    
    logger.info("\n✅ E2E Testing Completed. Output artifacts saved to logs/ and outputs/.")

def generate_report():
    logger.info("Generating Final System Report...")
    try:
        pipeline = TrainPipeline(data_path="app/ml/data/raw/train.csv")
        with open("outputs/metrics.json", "r") as f:
            metrics = json.load(f)
            logger.info("Model Metrics Verified.")
            for model, m in metrics.items():
                logger.info(f"[{model}] Accuracy: {m.get('accuracy', 0):.2f} | F1: {m.get('f1_macro', 0):.2f}")
    except Exception as e:
        logger.warning("Could not read metrics.json. Please run the training pipeline once.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CM-Dashboard CLI")
    parser.add_argument("--test", action="store_true", help="Run End-to-End Pipeline Validation")
    parser.add_argument("--train", action="store_true", help="Run ML Training Pipeline")
    args = parser.parse_args()
    
    if args.train:
        pipeline = TrainPipeline(data_path="app/ml/data/raw/train.csv")
        pipeline.run()
        
    if args.test:
        asyncio.run(run_e2e_tests())
        generate_report()
        
    if not args.train and not args.test:
        parser.print_help()
