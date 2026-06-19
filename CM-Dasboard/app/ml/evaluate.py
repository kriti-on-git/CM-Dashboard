import os
import json
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Optional
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, 
    confusion_matrix, classification_report, roc_curve, auc
)
from sklearn.preprocessing import label_binarize

logger = logging.getLogger(__name__)

class ModelEvaluator:
    """
    Advanced Model Evaluation Layer.
    Generates detailed metrics, confusion matrices, and distribution charts.
    """
    def __init__(self, output_dir: str = "outputs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Load existing metrics if any, to append or merge
        self.metrics_file = os.path.join(self.output_dir, "metrics.json")
        self.all_metrics = {}
        if os.path.exists(self.metrics_file):
            try:
                with open(self.metrics_file, "r") as f:
                    self.all_metrics = json.load(f)
            except json.JSONDecodeError:
                pass

    def check_data_imbalance(self, y_true: np.ndarray, y_pred: np.ndarray, classes: List[str], model_name: str):
        """Checks for class imbalances and logs warnings if necessary."""
        true_counts = pd.Series(y_true).value_counts()
        pred_counts = pd.Series(y_pred).value_counts()
        
        if len(true_counts) > 1:
            max_true = true_counts.max()
            min_true = true_counts.min()
            if min_true > 0 and max_true / min_true > 2.0:
                logger.warning(f"[{model_name}] Class imbalance detected! Max class '{classes[true_counts.idxmax()]}' is >2x larger than min class '{classes[true_counts.idxmin()]}'.")
                
        if len(pred_counts) > 0:
            dom_pred = pred_counts.max()
            if dom_pred / len(y_pred) > 0.8:
                logger.warning(f"[{model_name}] Dominant prediction detected! Class '{classes[pred_counts.idxmax()]}' predicted {dom_pred/len(y_pred)*100:.1f}% of the time.")

    def plot_confusion_matrix(self, y_true, y_pred, classes: List[str], model_name: str):
        """Generates and saves a seaborn heatmap for the confusion matrix."""
        cm = confusion_matrix(y_true, y_pred)
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=classes, yticklabels=classes)
        plt.title(f"{model_name} - Confusion Matrix")
        plt.ylabel('Actual')
        plt.xlabel('Predicted')
        plt.tight_layout()
        save_path = os.path.join(self.output_dir, f"{model_name.lower()}_confusion_matrix.png")
        plt.savefig(save_path)
        plt.close()
        logger.info(f"Saved confusion matrix to {save_path}")

    def plot_distributions(self, y_true, y_pred, classes: List[str], model_name: str):
        """Generates and saves bar charts comparing actual vs predicted distributions."""
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        
        # True Distribution
        true_counts = [np.sum(y_true == i) for i in range(len(classes))]
        axes[0].bar(classes, true_counts, color='skyblue')
        axes[0].set_title(f"{model_name} - Actual Class Distribution")
        axes[0].tick_params(axis='x', rotation=45)
        
        # Predicted Distribution
        pred_counts = [np.sum(y_pred == i) for i in range(len(classes))]
        axes[1].bar(classes, pred_counts, color='lightgreen')
        axes[1].set_title(f"{model_name} - Predicted Class Distribution")
        axes[1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        save_path = os.path.join(self.output_dir, f"{model_name.lower()}_class_distribution.png")
        plt.savefig(save_path)
        plt.close()
        logger.info(f"Saved distribution plot to {save_path}")

    def plot_roc_auc(self, y_true, y_prob, classes: List[str], model_name: str):
        """Generates ROC-AUC curve if probabilities are available."""
        if y_prob is None or len(np.unique(y_true)) < 2:
            return
            
        n_classes = len(classes)
        y_true_bin = label_binarize(y_true, classes=range(n_classes))
        
        plt.figure(figsize=(8, 6))
        
        for i in range(n_classes):
            if np.sum(y_true_bin[:, i]) > 0: # Ensure class is present
                fpr, tpr, _ = roc_curve(y_true_bin[:, i], y_prob[:, i])
                roc_auc = auc(fpr, tpr)
                plt.plot(fpr, tpr, lw=2, label=f'Class {classes[i]} (AUC = {roc_auc:.2f})')
                
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title(f'{model_name} - ROC Curve')
        plt.legend(loc="lower right")
        plt.tight_layout()
        
        save_path = os.path.join(self.output_dir, f"{model_name.lower()}_roc_curve.png")
        plt.savefig(save_path)
        plt.close()
        logger.info(f"Saved ROC curve to {save_path}")

    def evaluate(self, y_true: np.ndarray, y_pred: np.ndarray, model_name: str, label_encoder=None, y_prob: Optional[np.ndarray] = None):
        """
        Main evaluation function that computes metrics, checks imbalances, 
        and generates all requested graphs.
        """
        logger.info(f"\n{'='*40}\n{model_name.upper()} ADVANCED EVALUATION\n{'='*40}")
        
        classes = label_encoder.classes_ if label_encoder else [str(i) for i in np.unique(y_true)]
        
        self.check_data_imbalance(y_true, y_pred, classes, model_name)
        
        # 1. Compute Metrics
        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "precision_macro": float(precision_score(y_true, y_pred, average='macro', zero_division=0)),
            "precision_weighted": float(precision_score(y_true, y_pred, average='weighted', zero_division=0)),
            "recall_macro": float(recall_score(y_true, y_pred, average='macro', zero_division=0)),
            "recall_weighted": float(recall_score(y_true, y_pred, average='weighted', zero_division=0)),
            "f1_macro": float(f1_score(y_true, y_pred, average='macro', zero_division=0)),
            "f1_weighted": float(f1_score(y_true, y_pred, average='weighted', zero_division=0))
        }
        
        logger.info(f"Accuracy: {metrics['accuracy']:.4f}")
        logger.info(f"F1 (Macro): {metrics['f1_macro']:.4f} | F1 (Weighted): {metrics['f1_weighted']:.4f}")
        
        logger.info("\nClassification Report:")
        logger.info("\n" + classification_report(y_true, y_pred, target_names=classes, zero_division=0))
        
        # 2. Save Metrics to JSON
        self.all_metrics[model_name] = metrics
        with open(self.metrics_file, "w") as f:
            json.dump(self.all_metrics, f, indent=4)
        logger.info(f"Appended metrics to {self.metrics_file}")
            
        # 3. Visualizations
        self.plot_confusion_matrix(y_true, y_pred, classes, model_name)
        self.plot_distributions(y_true, y_pred, classes, model_name)
        
        if y_prob is not None:
            self.plot_roc_auc(y_true, y_prob, classes, model_name)
            
        logger.info("="*40)
        return metrics
