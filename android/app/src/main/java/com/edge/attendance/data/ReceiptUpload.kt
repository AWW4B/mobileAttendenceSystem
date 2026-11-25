package com.edge.attendance.data

import android.content.Context
import android.util.Log
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Store-and-forward for MEC receipts. A receipt holds only pseudonyms and is
 * signed by the MEC, so it is safe to keep on the phone until the portal is
 * reachable (e.g. campus Wi-Fi reaches the MEC but not the internet).
 */
class ReceiptQueue(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("receipt_queue", Context.MODE_PRIVATE)

    @Synchronized fun add(receipt: String) {
        prefs.edit().putStringSet(KEY, all() + receipt).apply()
    }

    @Synchronized fun remove(receipt: String) {
        prefs.edit().putStringSet(KEY, all() - receipt).apply()
    }

    @Synchronized fun all(): Set<String> = prefs.getStringSet(KEY, emptySet())!!.toSet()

    private companion object { const val KEY = "pending" }
}

class ReceiptUploadWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val queue = ReceiptQueue(applicationContext)
        val portal = PortalClient(Http.client(applicationContext), AppPrefs(applicationContext).portalUrl)
        var retry = false
        for (receipt in queue.all()) {
            try {
                portal.postReceipt(receipt)
                queue.remove(receipt)
            } catch (e: ApiException) {
                if (e.code in 400..499 && e.code != 408 && e.code != 429) {
                    Log.w(TAG, "Portal rejected a receipt (${e.code}: ${e.message}); dropping it")
                    queue.remove(receipt)
                } else {
                    retry = true
                }
            } catch (e: IOException) {
                retry = true
            }
        }
        return if (retry) Result.retry() else Result.success()
    }

    companion object {
        private const val TAG = "ReceiptUpload"

        fun schedule(context: Context) {
            val request = OneTimeWorkRequestBuilder<ReceiptUploadWorker>()
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context)
                .enqueueUniqueWork("receipt-upload", ExistingWorkPolicy.REPLACE, request)
        }
    }
}
