package com.edge.attendance

import com.edge.attendance.data.Http
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ServerCodeTest {
    private val der = "abc".toByteArray() // SHA-256 starts ba7816bf8f01cfea

    @Test fun matchesPrefixIgnoringCaseAndSeparators() = assertTrue(Http.matchesServerCode(der, "BA78-16BF 8F01-CFEA"))

    @Test fun rejectsShortWrongOrEmpty() {
        assertFalse(Http.matchesServerCode(der, "ba7816bf"))
        assertFalse(Http.matchesServerCode(der, "ba7816bf8f01cfeb"))
        assertFalse(Http.matchesServerCode(der, ""))
    }
}
